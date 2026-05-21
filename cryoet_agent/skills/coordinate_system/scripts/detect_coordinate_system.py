#!/usr/bin/env python3
"""
Analyze the source code of a cryo-ET reconstruction tool to identify its
coordinate system conventions relative to the IMOD reference.

This script scans source files for patterns that reveal:
- Axis ordering (memory layout)
- FFT dimension mapping
- Rotation/tilt axis identity
- Back-projection direction (Z sign)
- MRC header dimension assignment

Usage:
    python detect_coordinate_system.py --source-dir /path/to/software/src
    python detect_coordinate_system.py --source-dir /path/to/src --language cuda --output report.json
    python detect_coordinate_system.py --source-dir /path/to/src --list-files  # List supported file types
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Pattern definitions for each category
# ---------------------------------------------------------------------------

# 1. FFT dimension patterns
FFT_PATTERNS = {
    "cufft": {
        "pattern": re.compile(
            r"cufftPlan3d\s*\(\s*\w+\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*[,)]",
            re.IGNORECASE
        ),
        "type": "cuda",
        "library": "cuFFT",
        "interpretation": "cuFFT 3D plan dimensions (nz, ny, nx) for IMOD-compatible",
    },
    "fftw": {
        "pattern": re.compile(
            r"fftw_plan_dft_3d\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,",
            re.IGNORECASE
        ),
        "type": "c",
        "library": "FFTW",
        "interpretation": "FFTW 3D plan dimensions (nz, ny, nx) for IMOD-compatible",
    },
    "mkl_fft": {
        "pattern": re.compile(
            r"DftiCreateDescriptor\w*\s*\([^,]+,\s*[^,]+,\s*[^,]+,\s*\d+\s*,\s*\[\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\]",
            re.IGNORECASE
        ),
        "type": "fortran",
        "library": "MKL-FFT",
        "interpretation": "MKL FFT 3D descriptor dimensions (Fortran order: nx, ny, nz for IMOD-internal)",
    },
}

# 2. Rotation matrix patterns (tilt axis identification)
TILT_AXIS_PATTERNS = {
    "rotation_y": {
        "pattern": re.compile(
            r"(?:rotation|rotate).*?(?:tilt|angle).*?(?:axis|around|about)\s*[=:]?\s*['\"]?\s*Y\b",
            re.IGNORECASE
        ),
        "indicates": "Tilt axis is Y (IMOD-compatible)",
    },
    "rotation_x": {
        "pattern": re.compile(
            r"(?:rotation|rotate).*?(?:tilt|angle).*?(?:axis|around|about)\s*[=:]?\s*['\"]?\s*X\b",
            re.IGNORECASE
        ),
        "indicates": "Tilt axis is X (NOT IMOD-compatible — axes likely swapped)",
    },
    "ry_matrix": {
        "pattern": re.compile(
            r"Ry\s*\(\s*\w*\s*\)|rotation[_-]?y|rot[_-]?y|tilt[_-]?y",
            re.IGNORECASE
        ),
        "indicates": "Rotation matrix Ry — tilt axis is Y (IMOD-compatible)",
    },
    "rx_matrix": {
        "pattern": re.compile(
            r"Rx\s*\(\s*\w*\s*\)|rotation[_-]?x|rot[_-]?x|tilt[_-]?x",
            re.IGNORECASE
        ),
        "indicates": "Rotation matrix Rx — tilt axis is X (NOT IMOD-compatible)",
    },
}

# 3. Back-projection direction patterns
BACKPROJECTION_PATTERNS = {
    "positive_z_beam": {
        "pattern": re.compile(
            r"(?:proj|projected|back[_-]?proj).*?(?:z|depth).*?\+.*?(?:cos|sin).*?(?:tilt|angle|alpha)",
            re.IGNORECASE
        ),
        "indicates": "Back-projection uses +Z direction (IMOD-compatible)",
    },
    "negative_z_beam": {
        "pattern": re.compile(
            r"(?:proj|projected|back[_-]?proj).*?(?:z|depth).*?\-\s*.*?(?:cos|sin).*?(?:tilt|angle|alpha)",
            re.IGNORECASE
        ),
        "indicates": "Back-projection uses -Z direction (Z is flipped vs IMOD)",
    },
    "lookat_lh": {
        "pattern": re.compile(
            r"LookAtLH|CreateLookAt.*?(?:LH|LeftHand)",
            re.IGNORECASE
        ),
        "indicates": "Left-handed coordinate system (Z likely flipped vs IMOD)",
    },
    "lookat_rh": {
        "pattern": re.compile(
            r"LookAtRH|CreateLookAt.*?(?:RH|RightHand)",
            re.IGNORECASE
        ),
        "indicates": "Right-handed coordinate system (IMOD-compatible)",
    },
}

# 4. MRC header dimension assignment
MRC_HEADER_PATTERNS = {
    "dim_assignment": {
        "pattern": re.compile(
            r"(?:header|mrc|mrcHeader)\s*(?:\.|->)\s*(?:nx|ny|nz)\s*=\s*(\w+)",
            re.IGNORECASE
        ),
        "indicates": "MRC header dimension assignment — check variable names",
    },
    "swap_comment": {
        "pattern": re.compile(
            r"(?:swap|transpose|permute|reorder|flip|invert).*?(?:axis|coord|dim|X|Y|Z)",
            re.IGNORECASE
        ),
        "indicates": "Explicit mention of axis manipulation in comments",
    },
}

# 5. Memory layout patterns (loops)
MEMORY_LAYOUT_PATTERNS = {
    "triple_loop_c": {
        "pattern": re.compile(
            r"for\s*\([^;]*z\b[^;]*;[^;]*;[^)]*\)\s*"
            r"for\s*\([^;]*y\b[^;]*;[^;]*;[^)]*\)\s*"
            r"for\s*\([^;]*x\b[^;]*;[^;]*;[^)]*\)",
            re.IGNORECASE | re.DOTALL
        ),
        "indicates": "C-style Z-outmost, X-innermost loop → X is fast (IMOD-compatible)",
    },
    "triple_loop_fortran": {
        "pattern": re.compile(
            r"(?:do|DO)\s+\w*z\w*\s*=.*?\n\s*"
            r"(?:do|DO)\s+\w*y\w*\s*=.*?\n\s*"
            r"(?:do|DO)\s+\w*x\w*\s*=.*?",
            re.IGNORECASE | re.DOTALL
        ),
        "indicates": "Fortran-style Z-outmost, X-innermost loop → X is contiguous (Fortran column-major)",
    },
    "cuda_grid_3d": {
        "pattern": re.compile(
            r"dim3\s+\w*(?:grid|block|thread)\w*\s*\([^)]+\)",
            re.IGNORECASE
        ),
        "indicates": "CUDA 3D grid — check thread-to-axis mapping",
    },
}

# 6. Comments mentioning coordinate conventions
COMMENT_PATTERNS = {
    "imod_reference": {
        "pattern": re.compile(
            r"IMOD|imod",
            re.IGNORECASE
        ),
        "indicates": "References IMOD coordinate conventions",
    },
    "coord_documentation": {
        "pattern": re.compile(
            r"(?:coordinate|axis|axes|handedness|left.hand|right.hand)\s*(?:system|convention|definition|order)",
            re.IGNORECASE
        ),
        "indicates": "Explicit coordinate system documentation in comments",
    },
    "transpose_comment": {
        "pattern": re.compile(
            r"(?:transpose|permute|swap|flip|reverse|invert).*?(?:axes?|dimensions?|coordinates?|X|Y|Z)",
            re.IGNORECASE
        ),
        "indicates": "Axis manipulation documented in comments",
    },
}

# File extensions to scan
LANGUAGE_EXTENSIONS = {
    "c": {".c", ".h"},
    "cpp": {".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".cuh"},
    "cuda": {".cu", ".cuh"},
    "fortran": {".f", ".f90", ".f95", ".f03", ".f08", ".for"},
    "csharp": {".cs"},
    "python": {".py", ".pyx"},
    "matlab": {".m"},
}

# Extensions to include for comment scanning (all text-like files)
COMMENT_SCAN_EXTENSIONS = {".txt", ".md", ".rst", ".tex", ".bib"}


# ---------------------------------------------------------------------------
# Core scanning logic
# ---------------------------------------------------------------------------

def find_source_files(source_dir: Path, languages: list[str] | None = None) -> list[Path]:
    """
    Find all source files in the given directory matching supported languages.

    Args:
        source_dir: Root directory to scan
        languages: Language tags to include (None = all supported)

    Returns:
        Sorted list of Path objects
    """
    if languages:
        extensions = set()
        for lang in languages:
            if lang in LANGUAGE_EXTENSIONS:
                extensions.update(LANGUAGE_EXTENSIONS[lang])
    else:
        extensions = set()
        for exts in LANGUAGE_EXTENSIONS.values():
            extensions.update(exts)
        extensions.update(COMMENT_SCAN_EXTENSIONS)

    files = []
    for ext in extensions:
        files.extend(source_dir.rglob(f"*{ext}"))

    return sorted(set(files))


def scan_file_for_patterns(filepath: Path, pattern_dict: dict) -> list[dict]:
    """
    Scan a single file for matches of the given pattern dictionary.

    Args:
        filepath: Path to source file
        pattern_dict: Dict of {name: {"pattern": compiled_regex, "indicates": str, ...}}

    Returns:
        List of match dicts with file, line, match context, and interpretation
    """
    matches = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return matches

    lines = content.splitlines()
    for name, spec in pattern_dict.items():
        for match in spec["pattern"].finditer(content):
            # Find line number
            pos = match.start()
            line_num = content[:pos].count("\n") + 1

            # Get context (surrounding lines)
            start_line = max(0, line_num - 2)
            end_line = min(len(lines), line_num + 2)
            context = "\n".join(
                f"  {i+1}: {lines[i]}" for i in range(start_line, end_line)
            )

            matches.append({
                "pattern_name": name,
                "file": str(filepath),
                "line": line_num,
                "match": match.group(0)[:200],  # Truncate long matches
                "interpretation": spec["indicates"],
                "context": context,
            })

    return matches


def analyze_fft_dimensions(fft_matches: list[dict]) -> dict:
    """
    Analyze FFT plan dimension matches to determine axis ordering.

    Returns dict with axis_order, compatibility assessment.
    """
    result = {
        "matches_found": len(fft_matches),
        "observations": [],
        "likely_axis_order": "unknown",
    }

    for m in fft_matches:
        result["observations"].append({
            "file": m["file"],
            "line": m["line"],
            "library": m.get("library", "unknown"),
            "interpretation": m["interpretation"],
        })

    return result


def analyze_tilt_axis(tilt_matches: list[dict]) -> dict:
    """Determine tilt axis identity from matches."""
    y_matches = sum(1 for m in tilt_matches
                    if "IMOD-compatible" in m.get("interpretation", ""))
    x_matches = sum(1 for m in tilt_matches
                    if "NOT IMOD-compatible" in m.get("interpretation", ""))

    if y_matches > x_matches and y_matches > 0:
        tilt_axis = "Y (IMOD-compatible)"
        confidence = "high" if x_matches == 0 else "moderate"
    elif x_matches > y_matches and x_matches > 0:
        tilt_axis = "X (NOT IMOD-compatible — likely axis swap needed)"
        confidence = "high" if y_matches == 0 else "moderate"
    else:
        tilt_axis = "undetermined"
        confidence = "low"

    return {
        "tilt_axis": tilt_axis,
        "confidence": confidence,
        "y_axis_matches": y_matches,
        "x_axis_matches": x_matches,
    }


def analyze_backprojection(bp_matches: list[dict]) -> dict:
    """Analyze back-projection direction."""
    positive_z = sum(1 for m in bp_matches
                     if "IMOD-compatible" in m.get("interpretation", ""))
    negative_z = sum(1 for m in bp_matches
                     if "flipped vs IMOD" in m.get("interpretation", ""))
    left_handed = sum(1 for m in bp_matches
                      if "Left-handed" in m.get("interpretation", ""))
    right_handed = sum(1 for m in bp_matches
                       if "Right-handed" in m.get("interpretation", ""))

    if right_handed > left_handed or positive_z > negative_z:
        z_direction = "+Z (IMOD-compatible right-handed)"
    elif left_handed > right_handed or negative_z > positive_z:
        z_direction = "-Z (flipped vs IMOD, likely left-handed)"
    else:
        z_direction = "undetermined"

    return {
        "z_direction": z_direction,
        "positive_z_matches": positive_z,
        "negative_z_matches": negative_z,
        "left_handed_references": left_handed,
        "right_handed_references": right_handed,
    }


def generate_transformation_hypothesis(
    fft_analysis: dict,
    tilt_analysis: dict,
    bp_analysis: dict,
    mrc_matches: list[dict],
) -> dict:
    """
    Combine all analyses into a best-guess transformation to IMOD coordinates.

    Returns:
        Dict with permutation, flips, and confidence.
    """
    permute = (0, 1, 2)  # Default: no permutation
    flips = (False, False, False)  # Default: no flips

    reasons = []

    # Check if tilt axis is X (need Y↔swap)
    if "NOT IMOD-compatible" in tilt_analysis.get("tilt_axis", ""):
        permute = (0, 2, 1)  # Swap Y and Z (index 1 and 2)
        reasons.append("Tilt axis detected as X (not Y) → likely Y↔Z swap needed")

    # Check Z direction
    if "flipped vs IMOD" in bp_analysis.get("z_direction", ""):
        flips = (True, False, False)  # Flip Z
        reasons.append("Z direction flipped (left-handed) → flip Z axis needed")

    # Check for explicit swap mentions
    for m in mrc_matches:
        if "swap" in m.get("match", "").lower() and "xy" in m.get("match", "").lower():
            permute = (0, 2, 1)  # X↔Y swap
            reasons.append(f"Explicit X↔Y swap found in MRC I/O: {m['file']}:{m['line']}")

    # Confidence assessment
    num_sources = sum([
        bool(fft_analysis.get("matches_found", 0)),
        bool(tilt_analysis.get("y_axis_matches", 0) + tilt_analysis.get("x_axis_matches", 0)),
        bool(bp_analysis.get("positive_z_matches", 0) + bp_analysis.get("negative_z_matches", 0)),
    ])
    confidence = {3: "high", 2: "moderate", 1: "low", 0: "none"}[num_sources]

    return {
        "permutation": permute,
        "flips": flips,
        "confidence": confidence,
        "reasons": reasons if reasons else ["No transformation criteria detected — assume IMOD-compatible"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect coordinate system conventions from source code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source-dir /path/to/aretomo/src --language cuda
  %(prog)s --source-dir /path/to/warp/src --language csharp
  %(prog)s --source-dir /path/to/software --output report.json
  %(prog)s --source-dir /path/to/src --list-files  # Only list files
        """,
    )
    parser.add_argument("-d", "--source-dir", required=True,
                        help="Root directory of the reconstruction software source code")
    parser.add_argument("-l", "--language", choices=list(LANGUAGE_EXTENSIONS),
                        help="Programming language to focus on (default: scan all)")
    parser.add_argument("-o", "--output",
                        help="Save JSON report to file")
    parser.add_argument("--list-files", action="store_true",
                        help="List source files found and exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print all matches with context")

    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"Error: Directory not found: {args.source_dir}", file=sys.stderr)
        sys.exit(1)

    # Find files
    languages = [args.language] if args.language else None
    files = find_source_files(source_dir, languages)
    print(f"Found {len(files)} source files in: {source_dir}")

    if args.list_files:
        for f in files:
            print(f"  {f.relative_to(source_dir)}")
        sys.exit(0)

    # Scan for patterns
    all_patterns = {
        **FFT_PATTERNS,
        **TILT_AXIS_PATTERNS,
        **BACKPROJECTION_PATTERNS,
        **MRC_HEADER_PATTERNS,
        **MEMORY_LAYOUT_PATTERNS,
        **COMMENT_PATTERNS,
    }

    all_matches = []
    for filepath in files:
        matches = scan_file_for_patterns(filepath, all_patterns)
        all_matches.extend(matches)
        if matches and args.verbose:
            print(f"\n--- {filepath.relative_to(source_dir)} ({len(matches)} matches) ---")
            for m in matches:
                print(f"  [{m['pattern_name']}] L{m['line']}: {m['match'][:100]}")
                if args.verbose:
                    print(m['context'])
                    print()

    # Group matches by category
    categorized = defaultdict(list)
    for m in all_matches:
        if m["pattern_name"] in FFT_PATTERNS:
            categorized["fft"].append(m)
        elif m["pattern_name"] in TILT_AXIS_PATTERNS:
            categorized["tilt_axis"].append(m)
        elif m["pattern_name"] in BACKPROJECTION_PATTERNS:
            categorized["backprojection"].append(m)
        elif m["pattern_name"] in MRC_HEADER_PATTERNS:
            categorized["mrc_header"].append(m)
        elif m["pattern_name"] in MEMORY_LAYOUT_PATTERNS:
            categorized["memory_layout"].append(m)
        elif m["pattern_name"] in COMMENT_PATTERNS:
            categorized["comments"].append(m)

    # Analyze each category
    fft_analysis = analyze_fft_dimensions(categorized["fft"])
    tilt_analysis = analyze_tilt_axis(categorized["tilt_axis"])
    bp_analysis = analyze_backprojection(categorized["backprojection"])
    transformation = generate_transformation_hypothesis(
        fft_analysis, tilt_analysis, bp_analysis, categorized["mrc_header"]
    )

    # Build report
    report = {
        "source_directory": str(source_dir),
        "files_scanned": len(files),
        "total_matches": len(all_matches),
        "categories": {
            "fft_plans": {
                "matches": len(categorized["fft"]),
                "analysis": fft_analysis,
            },
            "tilt_axis": {
                "matches": len(categorized["tilt_axis"]),
                "analysis": tilt_analysis,
            },
            "backprojection": {
                "matches": len(categorized["backprojection"]),
                "analysis": bp_analysis,
            },
            "mrc_header": {
                "matches": len(categorized["mrc_header"]),
                "sample_matches": [{"file": m["file"], "line": m["line"],
                                    "match": m["match"]}
                                   for m in categorized["mrc_header"][:10]],
            },
            "memory_layout": {
                "matches": len(categorized["memory_layout"]),
                "sample_matches": [{"file": m["file"], "line": m["line"],
                                    "interpretation": m.get("interpretation")}
                                   for m in categorized["memory_layout"][:10]],
            },
            "comments": {
                "matches": len(categorized["comments"]),
                "sample_matches": [{"file": m["file"], "line": m["line"],
                                    "match": m["match"]}
                                   for m in categorized["comments"][:20]],
            },
        },
        "inferred_transformation": {
            "axes_permutation": transformation["permutation"],
            "axis_flips": transformation["flips"],
            "confidence": transformation["confidence"],
            "reasons": transformation["reasons"],
        },
        "recommendation": (
            "Use convert_tomogram.py with the inferred permutation and flips. "
            "Then validate with validate_coordinate_system.py against an IMOD reconstruction."
        ),
    }

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport saved: {args.output}")
    else:
        print("\n" + "=" * 60)
        print("Coordinate System Detection Report")
        print("=" * 60)

        print(f"\nSource: {source_dir}")
        print(f"Files scanned: {len(files)}")
        print(f"Total pattern matches: {len(all_matches)}")

        print(f"\n--- FFT Plans ---")
        print(f"  Matches: {len(categorized['fft'])}")
        for obs in fft_analysis.get("observations", []):
            print(f"  - {obs['library']}: {obs['file']}:{obs['line']}")

        print(f"\n--- Tilt Axis ---")
        print(f"  Detected: {tilt_analysis['tilt_axis']}")
        print(f"  Confidence: {tilt_analysis['confidence']}")

        print(f"\n--- Back-Projection Direction ---")
        print(f"  Detected: {bp_analysis['z_direction']}")

        print(f"\n--- Inferred Transformation to IMOD ---")
        print(f"  Permutation: {transformation['permutation']}")
        print(f"  Flips: {transformation['flips']}")
        print(f"  Confidence: {transformation['confidence']}")
        for reason in transformation["reasons"]:
            print(f"  → {reason}")

        if categorized["comments"]:
            print(f"\n--- Relevant Comments ({len(categorized['comments'])} matches) ---")
            seen = set()
            for m in categorized["comments"][:10]:
                key = (m["file"], m["match"])
                if key not in seen:
                    print(f"  {m['file']}:{m['line']} — {m['match'][:120]}")
                    seen.add(key)

        print(f"\n{report['recommendation']}")


if __name__ == "__main__":
    main()
