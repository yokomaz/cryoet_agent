#!/usr/bin/env python3
"""
Empirically validate the coordinate system of a tomogram by comparing against
an IMOD reconstruction of the same tilt series.

This script:
1. Loads a source tomogram and an IMOD reference tomogram
2. Searches for the optimal 3D affine transformation (flip, swap, rotation)
   that maximizes the cross-correlation between the two volumes
3. Reports the best-fit transformation

Usage:
    python validate_coordinate_system.py \
        --source tomo_aretomo.mrc \
        --reference tomo_imod.mrc \
        --output transform.txt

    python validate_coordinate_system.py \
        --source tomo_warp.mrc \
        --reference tomo_imod.mrc \
        --exhaustive \
        --output transform.txt
"""

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Transformation candidate generation
# ---------------------------------------------------------------------------

def generate_candidate_transforms(include_rotations: bool = False) -> list[dict]:
    """
    Generate all plausible coordinate transformations to IMOD.

    Each transform is a dict with:
      - name: human-readable name
      - permute: axis permutation tuple (3,)
      - flips: axis flip booleans (3,)

    By default, only permutations and flips are checked (no full rotation).
    If include_rotations=True, includes 90-degree rotations.

    Returns:
        List of transform candidate dicts
    """
    candidates = []

    # All axis permutations
    perms = list(itertools.permutations([0, 1, 2]))

    # All axis flip combinations
    flips = list(itertools.product([False, True], repeat=3))

    for perm in perms:
        for flip in flips:
            # Skip identity (perm=(0,1,2), flips=(F,F,F))
            if perm == (0, 1, 2) and flip == (False, False, False):
                name = "identity (IMOD-compatible)"
            else:
                desc_parts = []
                if perm != (0, 1, 2):
                    axis_names = ["Z", "Y", "X"]
                    desc = "→".join(axis_names[i] for i in perm)
                    desc_parts.append(f"permute({desc})")
                if any(flip):
                    flipped = [axis_names[i] for i, f in enumerate(flip) if f]
                    desc_parts.append(f"flip({','.join(flipped)})")
                name = ", ".join(desc_parts)

            candidates.append({
                "name": name,
                "permute": perm,
                "flips": flip,
            })

    return candidates


def apply_transform(volume: np.ndarray, transform: dict) -> np.ndarray:
    """Apply a coordinate transformation to a volume."""
    vol = np.transpose(volume, transform["permute"])
    for axis in range(3):
        if transform["flips"][axis]:
            vol = np.flip(vol, axis=axis)
    return vol


# ---------------------------------------------------------------------------
# Cross-correlation scoring
# ---------------------------------------------------------------------------

def normalize_volume(vol: np.ndarray) -> np.ndarray:
    """Normalize volume to zero mean and unit variance."""
    v = vol.astype(np.float64)
    v = v - v.mean()
    std = v.std()
    if std > 0:
        v = v / std
    return v


def compute_ncc(vol1: np.ndarray, vol2: np.ndarray,
                downsample: int = 2) -> float:
    """
    Compute the normalized cross-correlation between two volumes.

    To keep this fast for large volumes, the volumes are optionally
    downsampled before computing the correlation.

    Args:
        vol1, vol2: 3D volumes of the same shape
        downsample: Downsampling factor (1 = no downsampling)

    Returns:
        Normalized cross-correlation coefficient
    """
    if downsample > 1:
        slices = tuple(slice(None, None, downsample) for _ in range(3))
        vol1 = vol1[slices]
        vol2 = vol2[slices]

    v1 = normalize_volume(vol1)
    v2 = normalize_volume(vol2)

    # Flatten and compute NCC
    v1_flat = v1.ravel()
    v2_flat = v2.ravel()

    ncc = np.dot(v1_flat, v2_flat) / len(v1_flat)
    return float(ncc)


def compute_fft_correlation(vol1: np.ndarray, vol2: np.ndarray) -> float:
    """
    Compute correlation using FFT-based method (faster for large volumes).

    This computes the peak of the 3D cross-correlation in Fourier space.
    """
    f1 = np.fft.rfftn(normalize_volume(vol1))
    f2 = np.fft.rfftn(normalize_volume(vol2))

    # Cross-correlation via FFT
    cc = np.fft.irfftn(f1 * np.conj(f2))

    # Peak correlation value
    peak = np.max(cc)
    return float(peak)


# ---------------------------------------------------------------------------
# MRC I/O
# ---------------------------------------------------------------------------

def read_mrc(path: str) -> np.ndarray:
    """Read MRC volume data."""
    try:
        import mrcfile
    except ImportError:
        raise ImportError("mrcfile library is required. Install with: pip install mrcfile")

    with mrcfile.open(path, mode='r', permissive=True) as mrc:
        if mrc.data is None:
            raise ValueError(f"No data in MRC file: {path}")
        return mrc.data.copy()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def find_best_transform(
    source_vol: np.ndarray,
    ref_vol: np.ndarray,
    exhaustive: bool = False,
    top_k: int = 5,
) -> list[dict]:
    """
    Find the best coordinate transformation(s) that align source to reference.

    Args:
        source_vol: Source tomogram (3D array)
        ref_vol: IMOD reference tomogram (3D array)
        exhaustive: If True, test all 48 permutations+flips. If False,
                    test common cryo-ET transformations.
        top_k: Number of top results to return

    Returns:
        Sorted list of transform dicts with scores
    """
    if exhaustive:
        candidates = generate_candidate_transforms()
    else:
        # Common cryo-ET transformations only (more practical)
        candidates = [
            {"name": "identity (IMOD-compatible)", "permute": (0, 1, 2), "flips": (False, False, False)},
            {"name": "flip Z (Warp → IMOD)", "permute": (0, 1, 2), "flips": (True, False, False)},
            {"name": "swap X↔Y (AreTomo → IMOD)", "permute": (0, 2, 1), "flips": (False, False, False)},
            {"name": "swap X↔Y + flip Z", "permute": (0, 2, 1), "flips": (True, False, False)},
            {"name": "swap Y↔Z", "permute": (2, 1, 0), "flips": (False, False, False)},
            {"name": "swap Y↔Z + flip", "permute": (2, 1, 0), "flips": (True, False, False)},
            {"name": "flip X+Y (emClarity → IMOD)", "permute": (0, 1, 2), "flips": (False, True, True)},
            {"name": "flip X+Y+Z", "permute": (0, 1, 2), "flips": (True, True, True)},
            {"name": "swap X↔Y + flip X+Y", "permute": (0, 2, 1), "flips": (False, True, True)},
        ]

    # Ensure volumes are float64 and same size
    src = source_vol.astype(np.float64)
    ref = ref_vol.astype(np.float64)

    # If sizes differ, pad/crop to match
    if src.shape != ref.shape:
        print(f"Warning: Shape mismatch — source {src.shape}, reference {ref.shape}")
        min_shape = tuple(min(s, r) for s, r in zip(src.shape, ref.shape))
        src = src[:min_shape[0], :min_shape[1], :min_shape[2]]
        ref = ref[:min_shape[0], :min_shape[1], :min_shape[2]]
        print(f"  Cropped both to: {min_shape}")

    # Normalize reference once
    ref_norm = normalize_volume(ref)

    results = []
    for candidate in candidates:
        try:
            transformed = apply_transform(src, candidate)
            score = compute_ncc(transformed, ref, downsample=2)
            candidate["ncc_score"] = float(score)
            candidate["transformed_shape"] = transformed.shape
            results.append(candidate)
        except Exception as e:
            print(f"  Error with {candidate['name']}: {e}", file=sys.stderr)
            continue

    # Sort by NCC score (descending)
    results.sort(key=lambda x: x.get("ncc_score", -float("inf")), reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate coordinate system by comparing with IMOD reference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-s", "--source", required=True,
                        help="Source tomogram (.mrc)")
    parser.add_argument("-r", "--reference", required=True,
                        help="IMOD reference tomogram (.mrc)")
    parser.add_argument("-o", "--output",
                        help="Save best transformation to file")
    parser.add_argument("--exhaustive", action="store_true",
                        help="Test all 48 permutation+flip combinations")
    parser.add_argument("-k", "--top-k", type=int, default=5,
                        help="Number of top results to display (default: 5)")
    parser.add_argument("--json", help="Save full results as JSON")

    args = parser.parse_args()

    # Validate paths
    for path, label in [(args.source, "Source"), (args.reference, "Reference")]:
        if not Path(path).exists():
            print(f"Error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Read volumes
    print(f"Loading source: {args.source}")
    source_vol = read_mrc(args.source)
    print(f"  Shape: {source_vol.shape}")

    print(f"Loading reference: {args.reference}")
    ref_vol = read_mrc(args.reference)
    print(f"  Shape: {ref_vol.shape}")

    # Validate
    mode = "exhaustive (48 transforms)" if args.exhaustive else "common cryo-ET transforms"
    print(f"\nTesting transformations ({mode})...")
    print(f"  {'Rank':<6} {'Transform':<40} {'NCC Score':<12}")
    print(f"  {'-'*6} {'-'*40} {'-'*12}")

    results = find_best_transform(source_vol, ref_vol, exhaustive=args.exhaustive, top_k=args.top_k)

    for rank, r in enumerate(results, 1):
        print(f"  {rank:<6} {r['name']:<40} {r['ncc_score']:<12.6f}")

    # Best result
    best = results[0]
    print(f"\n=== Best Transformation ===")
    print(f"  Name:   {best['name']}")
    print(f"  Permutation: {best['permute']}")
    print(f"  Flips:  {best['flips']}")
    print(f"  NCC:    {best['ncc_score']:.6f}")

    # Check if second-best is close (ambiguity warning)
    if len(results) > 1:
        ratio = results[1]["ncc_score"] / max(best["ncc_score"], 1e-10)
        if ratio > 0.95:
            print(f"\n  ⚠  Warning: Second-best transform has very similar score ({ratio:.3f})")
            print(f"  Second: {results[1]['name']} (NCC={results[1]['ncc_score']:.6f})")
            print(f"  This may indicate the volumes are not from the same dataset,")
            print(f"  or the transformation is ambiguous. Manual verification recommended.")

    # Confidence assessment
    if best["ncc_score"] > 0.8:
        confidence = "high"
    elif best["ncc_score"] > 0.5:
        confidence = "moderate"
    elif best["ncc_score"] > 0.2:
        confidence = "low"
    else:
        confidence = "very low — volumes may be from different datasets"

    print(f"\n  Confidence: {confidence}")

    # Save output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(f"# Coordinate Transformation (source → IMOD)\n")
            f.write(f"# Source: {args.source}\n")
            f.write(f"# Reference: {args.reference}\n")
            f.write(f"# NCC Score: {best['ncc_score']:.6f}\n\n")
            f.write(f"permutation = {best['permute']}\n")
            f.write(f"flips = {best['flips']}\n")
            f.write(f"name = \"{best['name']}\"\n")
        print(f"\nTransformation saved: {args.output}")

    if args.json:
        import json
        with open(args.json, 'w') as f:
            json.dump({
                "source": args.source,
                "reference": args.reference,
                "best_transform": {
                    "name": best["name"],
                    "permutation": best["permute"],
                    "flips": best["flips"],
                    "ncc_score": best["ncc_score"],
                    "confidence": confidence,
                },
                "all_results": [
                    {"rank": i+1, "name": r["name"], "permutation": r["permute"],
                     "flips": r["flips"], "ncc_score": r["ncc_score"]}
                    for i, r in enumerate(results)
                ],
            }, f, indent=2)
        print(f"JSON report saved: {args.json}")


if __name__ == "__main__":
    main()
