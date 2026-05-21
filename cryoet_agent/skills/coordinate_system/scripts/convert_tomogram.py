#!/usr/bin/env python3
"""
Convert a tomogram from a known reconstruction software's coordinate system
into the IMOD reference coordinate system.

Supported sources: aretomo, warp, relion, novactf, emclarity

Usage:
    python convert_tomogram.py --input tomo.mrc --source aretomo --output imod_tomo.mrc
    python convert_tomogram.py --input tomo.mrc --source warp --output imod_tomo.mrc --save-transform
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Per-software transformation definitions
# ---------------------------------------------------------------------------

# Each entry: (axes_permutation, axe_flips, description)
# - axes_permutation: tuple of axis indices for np.transpose
# - axe_flips: tuple of booleans for np.flip along each axis AFTER permutation
TRANSFORMATIONS = {
    "imod": {
        "permute": (0, 1, 2),
        "flips": (False, False, False),
        "description": "IMOD (reference) — no transformation needed",
    },
    "aretomo": {
        # AreTomo GPU memory layout: X↔Y swapped relative to IMOD
        # Vol shape: [Z, X_imod, Y_imod] → [Z, Y_imod, X_imod] = [Z, Y, X] IMOD
        "permute": (0, 2, 1),
        "flips": (False, False, False),
        "description": "AreTomo → IMOD: swap X↔Y (GPU CUDA layout)",
    },
    "aretomo_v2": {
        # AreTomo 2.0+ reworked memory layout; may need different permutation
        "permute": (0, 2, 1),
        "flips": (False, False, False),
        "description": "AreTomo 2.0+ → IMOD: verify empirically; may need adjustment",
    },
    "warp": {
        # Warp uses left-handed Z (depth into screen); IMOD uses right-handed
        "permute": (0, 1, 2),
        "flips": (True, False, False),  # Flip Z (axis 0 in MRC layout)
        "description": "Warp → IMOD: flip Z (left-handed → right-handed)",
    },
    "relion4": {
        # RELION 4.0: Y↔Z may be swapped in reconstruction output
        "permute": (0, 2, 1),
        "flips": (False, False, False),
        "description": "RELION 4.0 → IMOD: swap Y↔Z (version-specific)",
    },
    "relion5": {
        # RELION 5.0+: IMOD-compatible
        "permute": (0, 1, 2),
        "flips": (False, False, False),
        "description": "RELION 5.0+ → IMOD: compatible, no transformation",
    },
    "novactf": {
        # novaCTF: generally IMOD-compatible with subvolume offset handling
        "permute": (0, 1, 2),
        "flips": (False, False, False),
        "description": "novaCTF → IMOD: compatible, check subvolume offsets",
    },
    "emclarity": {
        # emClarity: MATLAB conventions — X and Y may be flipped, Z may differ
        "permute": (0, 1, 2),
        "flips": (False, True, True),  # Flip X and Y
        "description": "emClarity → IMOD: flip X and Y (MATLAB array conventions)",
    },
}


# ---------------------------------------------------------------------------
# Core transformation
# ---------------------------------------------------------------------------

def apply_transformation(volume: np.ndarray, source: str) -> tuple[np.ndarray, dict]:
    """
    Apply coordinate transformation to convert a volume to IMOD coordinates.

    Args:
        volume: 3D numpy array [Z, Y, X] in source software's convention
        source: source software identifier (key in TRANSFORMATIONS)

    Returns:
        (transformed_volume, transform_info_dict)
    """
    if source not in TRANSFORMATIONS:
        available = ", ".join(sorted(TRANSFORMATIONS))
        raise ValueError(f"Unknown source '{source}'. Available: {available}")

    tx = TRANSFORMATIONS[source]

    # Step 1: Permute axes
    vol = np.transpose(volume, tx["permute"])

    # Step 2: Flip axes
    for axis, do_flip in enumerate(tx["flips"]):
        if do_flip:
            vol = np.flip(vol, axis=axis)

    info = {
        "source": source,
        "description": tx["description"],
        "permutation_applied": tx["permute"],
        "flips_applied": tx["flips"],
        "input_shape": volume.shape,
        "output_shape": vol.shape,
    }

    return vol, info


def build_affine_matrix(shape: tuple, tx_info: dict) -> np.ndarray:
    """
    Build a 4x4 affine transformation matrix describing the applied transform.

    This matrix maps IMOD physical coordinates to the source software's
    physical coordinates (inverse of the applied transformation).

    Returns:
        4x4 numpy array (homogeneous coordinates)
    """
    affine = np.eye(4)
    perm = tx_info["permutation_applied"]
    flips = tx_info["flips_applied"]

    # Build the 3x3 linear part from permutation and flips
    linear = np.zeros((3, 3))
    for src_axis, dst_axis in enumerate(perm):
        sign = -1 if flips[src_axis] else 1
        linear[dst_axis, src_axis] = sign

    affine[:3, :3] = linear
    return affine


# ---------------------------------------------------------------------------
# MRC I/O
# ---------------------------------------------------------------------------

def read_mrc(path: str) -> tuple[np.ndarray, dict]:
    """Read an MRC file. Returns (data, header_dict)."""
    try:
        import mrcfile
    except ImportError:
        raise ImportError("mrcfile library is required. Install with: pip install mrcfile")

    with mrcfile.open(path, mode='r', permissive=True) as mrc:
        data = mrc.data.copy()
        header = {
            "nx": int(mrc.header.nx),
            "ny": int(mrc.header.ny),
            "nz": int(mrc.header.nz),
            "mode": int(mrc.header.mode),
            "cella": {
                "x": float(mrc.header.cella.x),
                "y": float(mrc.header.cella.y),
                "z": float(mrc.header.cella.z),
            },
            "origin": {
                "x": float(mrc.header.origin.x),
                "y": float(mrc.header.origin.y),
                "z": float(mrc.header.origin.z),
            } if hasattr(mrc.header, 'origin') else None,
            "nxstart": int(mrc.header.nxstart),
            "nystart": int(mrc.header.nystart),
            "nzstart": int(mrc.header.nzstart),
        }
    return data, header


def write_mrc(path: str, data: np.ndarray, header: dict) -> None:
    """Write an MRC file with updated header."""
    try:
        import mrcfile
    except ImportError:
        raise ImportError("mrcfile library is required. Install with: pip install mrcfile")

    with mrcfile.new(path, overwrite=True) as mrc:
        mrc.set_data(data.astype(np.float32))
        mrc.header.nx = header["nx"]
        mrc.header.ny = header["ny"]
        mrc.header.nz = header["nz"]
        mrc.header.mode = header["mode"]
        mrc.header.cella.x = header["cella"]["x"]
        mrc.header.cella.y = header["cella"]["y"]
        mrc.header.cella.z = header["cella"]["z"]
        mrc.header.nxstart = header.get("nxstart", 0)
        mrc.header.nystart = header.get("nystart", 0)
        mrc.header.nzstart = header.get("nzstart", 0)
        if header.get("origin"):
            mrc.header.origin.x = header["origin"]["x"]
            mrc.header.origin.y = header["origin"]["y"]
            mrc.header.origin.z = header["origin"]["z"]


def update_header_for_imod(old_header: dict, new_shape: tuple, tx_info: dict) -> dict:
    """
    Update MRC header fields to reflect the transformation to IMOD coordinates.
    """
    new_header = old_header.copy()

    nx, ny, nz = new_shape[2], new_shape[1], new_shape[0]
    new_header["nx"] = nx
    new_header["ny"] = ny
    new_header["nz"] = nz

    # Adjust cella based on axis permutation
    old_cella = old_header["cella"]
    perm = tx_info["permutation_applied"]

    # Map old cella to new based on permutation
    old_dims = [old_header["nx"], old_header["ny"], old_header["nz"]]
    old_cella_vals = [old_cella["x"], old_cella["y"], old_cella["z"]]

    new_cella = [0.0, 0.0, 0.0]
    for src_axis, dst_axis in enumerate(perm):
        # MRC: X=nx, Y=ny, Z=nz
        # permutation indices: 0=Z, 1=Y, 2=X
        mrc_indices = {0: 2, 1: 1, 2: 0}  # perm_idx → MRC (X=2, Y=1, Z=0)
        src_mrc = mrc_indices[src_axis]
        dst_mrc = mrc_indices[dst_axis]
        new_cella[dst_mrc] = old_cella_vals[src_mrc]

    new_header["cella"]["x"] = new_cella[2]  # X
    new_header["cella"]["y"] = new_cella[1]  # Y
    new_header["cella"]["z"] = new_cella[0]  # Z

    # Reset origin to center (IMOD convention)
    if new_header["cella"]["x"] > 0:
        new_header["origin"] = {
            "x": new_header["cella"]["x"] / 2.0,
            "y": new_header["cella"]["y"] / 2.0,
            "z": new_header["cella"]["z"] / 2.0,
        }

    new_header["nxstart"] = 0
    new_header["nystart"] = 0
    new_header["nzstart"] = 0

    return new_header


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a tomogram to IMOD coordinate system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available source software keys:
  {', '.join(sorted(TRANSFORMATIONS))}

Examples:
  %(prog)s -i aretomo_tomo.mrc -s aretomo -o imod_tomo.mrc
  %(prog)s -i warp_tomo.mrc -s warp -o imod_tomo.mrc --save-transform
  %(prog)s -i unknown_tomo.mrc -s emclarity -o imod_tomo.mrc
        """,
    )
    parser.add_argument("-i", "--input", required=True,
                        help="Input tomogram (.mrc/.rec)")
    parser.add_argument("-s", "--source", required=True,
                        help="Source software key (see list below)")
    parser.add_argument("-o", "--output", required=True,
                        help="Output tomogram (.mrc) in IMOD coordinates")
    parser.add_argument("--save-transform", action="store_true",
                        help="Save transformation matrix to .txt file")
    parser.add_argument("--transform-output",
                        help="Path for transformation matrix file (default: <output>_transform.txt)")
    parser.add_argument("--json-report",
                        help="Save transformation report as JSON")

    args = parser.parse_args()

    # Validate input
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.source not in TRANSFORMATIONS:
        print(f"Error: Unknown source '{args.source}'", file=sys.stderr)
        print(f"Available: {', '.join(sorted(TRANSFORMATIONS))}", file=sys.stderr)
        sys.exit(1)

    # Read input
    print(f"Reading: {args.input}")
    vol, header = read_mrc(args.input)
    print(f"  Input shape: {vol.shape} (Z={vol.shape[0]}, Y={vol.shape[1]}, X={vol.shape[2]})")

    # Apply transformation
    print(f"Applying transformation: {args.source} → IMOD")
    print(f"  {TRANSFORMATIONS[args.source]['description']}")
    vol_imod, tx_info = apply_transformation(vol, args.source)
    print(f"  Output shape: {vol_imod.shape}")

    # Update header
    new_header = update_header_for_imod(header, vol_imod.shape, tx_info)

    # Write output
    write_mrc(args.output, vol_imod, new_header)
    print(f"Written: {args.output}")

    # Save transformation matrix
    if args.save_transform or args.transform_output:
        affine = build_affine_matrix(vol.shape, tx_info)
        matrix_path = args.transform_output or f"{Path(args.output).stem}_transform.txt"
        np.savetxt(matrix_path, affine, fmt="%.6f",
                   header="4x4 Affine transformation matrix (IMOD voxel coords → source voxel coords)")
        print(f"Transformation matrix saved: {matrix_path}")

    # Save JSON report
    if args.json_report:
        report = {
            **tx_info,
            "input_file": args.input,
            "output_file": args.output,
            "affine_matrix": build_affine_matrix(vol.shape, tx_info).tolist(),
        }
        with open(args.json_report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved: {args.json_report}")

    print("Done.")


if __name__ == "__main__":
    main()
