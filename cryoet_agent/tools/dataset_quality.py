"""
Dataset quality assessment tool for cryo-ET.

Reads a cryo-ET dataset directory and evaluates data quality across
multiple dimensions: tilt coverage, MRC stack statistics, alignment
drift, and CTF estimation quality.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np

WORKDIR = Path.cwd()


def _safe_path(path_str: str) -> Path:
    """Resolve path safely, preventing directory traversal."""
    path = (WORKDIR / path_str).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path_str}")
    return path


def _find_file(directory: Path, *patterns: str) -> Path | None:
    """Find the first file matching any of the given glob patterns in directory (recursive)."""
    for pattern in patterns:
        matches = list(directory.rglob(pattern))
        if matches:
            return matches[0]
    return None


def _read_tlt_file(path: Path) -> dict:
    """Read a .tlt or .rawtlt tilt angle file. Returns analysis dict."""
    lines = [l.strip() for l in path.read_text().strip().splitlines() if l.strip()]

    angles = [float(l) for l in lines]
    arr = np.array(angles)

    steps = np.diff(arr)
    median_step = float(np.median(steps))
    max_step_deviation = float(np.max(np.abs(steps - median_step)))

    # Detect missing tilts (gaps > 1.5x median step)
    missing_mask = np.abs(steps) > 1.5 * abs(median_step)
    missing_indices = [int(i) for i in np.where(missing_mask)[0]]

    # Find largest angular gap
    gaps = np.abs(np.diff(np.sort(arr)))
    largest_gap_idx = int(np.argmax(gaps))
    largest_gap = float(gaps[largest_gap_idx])
    largest_gap_between = (float(np.sort(arr)[largest_gap_idx]),
                           float(np.sort(arr)[largest_gap_idx + 1]))

    return {
        "file": str(path.name),
        "count": len(arr),
        "min_angle": float(np.min(arr)),
        "max_angle": float(np.max(arr)),
        "tilt_range": float(np.max(arr) - np.min(arr)),
        "median_step": round(median_step, 3),
        "step_consistency": {
            "max_deviation": round(max_step_deviation, 3),
            "is_uniform": max_step_deviation < 0.05,
        },
        "missing_tilts": {
            "gaps_count": len(missing_indices),
            "gap_positions": missing_indices,
        },
        "largest_gap": {
            "size_degrees": round(largest_gap, 2),
            "between": largest_gap_between,
        },
        "dose_symmetric": _check_dose_symmetry(arr),
    }


def _check_dose_symmetry(angles: np.ndarray) -> dict:
    """Check if tilt angles are symmetric (dose-symmetric scheme)."""
    # Dose-symmetric: starts at 0, goes negative then positive in alternating scheme
    # Bidirectional: starts at low tilt, progresses to high tilt
    if len(angles) < 2:
        return {"is_symmetric": False, "scheme": "unknown"}

    # Simple heuristic: check if angles are sorted by absolute value
    abs_angles = np.abs(angles)
    is_dose_symmetric = bool(np.all(np.diff(abs_angles[:10]) >= 0) or
                             np.all(np.diff(abs_angles[-10:]) <= 0))
    is_bidirectional = bool(np.all(np.diff(angles) >= 0) or
                            np.all(np.diff(angles) <= 0))

    if is_bidirectional:
        scheme = "bidirectional"
    elif is_dose_symmetric:
        scheme = "dose_symmetric"
    else:
        scheme = "other"

    return {"is_symmetric": is_dose_symmetric or is_bidirectional,
            "scheme": scheme}


def _read_xf_file(path: Path) -> dict:
    """Read an .xf alignment transformation file. Returns drift analysis."""
    lines = [l.strip() for l in path.read_text().strip().splitlines() if l.strip()]

    num_tilts = len(lines)
    translations = np.zeros((num_tilts, 2))

    for i, line in enumerate(lines):
        parts = line.split()
        if len(parts) >= 6:
            # .xf: A B C D X Y
            translations[i, 0] = float(parts[4])  # X shift
            translations[i, 1] = float(parts[5])  # Y shift

    # Cumulative drift (sum of absolute per-step shifts)
    per_step_drift = np.sqrt(np.sum(np.diff(translations, axis=0) ** 2, axis=1))
    cumulative_drift = float(np.sum(per_step_drift))
    max_step_drift = float(np.max(per_step_drift))
    mean_step_drift = float(np.mean(per_step_drift))

    # Total translation range
    total_x_range = float(np.max(translations[:, 0]) - np.min(translations[:, 0]))
    total_y_range = float(np.max(translations[:, 1]) - np.min(translations[:, 1]))

    return {
        "file": str(path.name),
        "num_transforms": num_tilts,
        "drift_analysis": {
            "cumulative_drift_pixels": round(cumulative_drift, 2),
            "max_per_step_drift": round(max_step_drift, 2),
            "mean_per_step_drift": round(mean_step_drift, 2),
            "total_x_range": round(total_x_range, 1),
            "total_y_range": round(total_y_range, 1),
        },
        "assessment": _assess_alignment_drift(cumulative_drift, mean_step_drift),
    }


def _assess_alignment_drift(cumulative: float, mean_step: float) -> str:
    """Qualitative assessment of alignment drift."""
    if mean_step < 1.0:
        return "excellent"
    elif mean_step < 3.0:
        return "good"
    elif mean_step < 10.0:
        return "moderate_drift"
    else:
        return "high_drift"


def _read_ctf_file(path: Path) -> dict:
    """Read a CTF estimation output file (ctffind4 / ctffind format)."""
    text = path.read_text().strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Parse data lines (skip headers)
    data_lines = []
    for line in lines:
        if line.startswith("#"):
            continue
        parts = line.split()
        try:
            float(parts[0])
            data_lines.append(parts)
        except (ValueError, IndexError):
            continue

    if not data_lines:
        return {"file": str(path.name), "status": "unparseable"}

    # Find the most common column count to handle inconsistent rows
    from collections import Counter
    col_counts = Counter(len(row) for row in data_lines)
    common_cols = col_counts.most_common(1)[0][0]
    data_lines = [row for row in data_lines if len(row) == common_cols]

    if not data_lines:
        return {"file": str(path.name), "status": "unparseable", "error": "No consistent column count"}

    num_tilts = len(data_lines)

    result = {
        "file": str(path.name),
        "tilts_with_ctf": num_tilts,
        "columns_detected": common_cols,
    }

    try:
        numeric_data = np.array([[float(v) for v in row] for row in data_lines])

        # Use last 3 columns as: defocus1, defocus2, quality_score
        defocus1_col = numeric_data[:, -3]
        defocus2_col = numeric_data[:, -2]
        quality_col = numeric_data[:, -1]

        result["defocus"] = {
            "mean_defocus1_a": round(float(np.mean(defocus1_col)), 0),
            "mean_defocus2_a": round(float(np.mean(defocus2_col)), 0),
            "defocus_range_a": [round(float(np.min(defocus1_col)), 0),
                                round(float(np.max(defocus2_col)), 0)],
            "mean_astigmatism_a": round(float(np.mean(np.abs(defocus1_col - defocus2_col))), 1),
        }

        result["ctf_quality"] = {
            "mean_score": round(float(np.mean(quality_col)), 2),
            "min_score": round(float(np.min(quality_col)), 2),
            "max_score": round(float(np.max(quality_col)), 2),
            "low_quality_tilts": int(np.sum(np.abs(quality_col) < 10)),
        }
    except Exception as e:
        result["parse_error"] = str(e)

    result["assessment"] = _assess_ctf_quality(result)
    return result


def _assess_ctf_quality(ctf_data: dict) -> str:
    """Qualitative assessment of CTF quality."""
    if "ctf_quality" not in ctf_data:
        return "unknown"

    q = ctf_data["ctf_quality"]
    low_count = q.get("low_quality_tilts", 0)
    num_tilts = ctf_data.get("tilts_with_ctf", 1)
    low_ratio = low_count / max(num_tilts, 1)

    if low_ratio < 0.1 and q["mean_score"] > 50:
        return "excellent"
    elif low_ratio < 0.2:
        return "good"
    elif low_ratio < 0.5:
        return "moderate"
    else:
        return "poor"


def _read_mrc_header(path: Path) -> dict:
    """Read MRC file header and compute per-slice statistics (memory-efficient)."""
    try:
        import mrcfile
    except ImportError:
        return {"error": "mrcfile library not available"}

    result = {"file": str(path.name), "file_size_mb": round(path.stat().st_size / (1024 * 1024), 1)}

    try:
        with mrcfile.mmap(str(path), permissive=True, mode='r') as mrc:
            header = mrc.header
            data = mrc.data

            if data is None:
                return _read_mrc_via_open(path)

            result["dimensions"] = {
                "nx": int(header.nx),
                "ny": int(header.ny),
                "nz": int(header.nz),
            }
            result["pixel_size"] = {
                "x_a": float(header.cella.x / header.nx) if header.nx > 0 else 0,
                "y_a": float(header.cella.y / header.ny) if header.ny > 0 else 0,
            } if header.cella.x > 0 else None
            result["data_type"] = int(header.mode)

            nz = header.nz
            slice_stats = []
            for i in range(nz):
                if nz > 10 and i % max(1, nz // 10) != 0 and i not in (0, nz - 1):
                    continue
                sl = data[i]
                sl_vals = sl[sl != 0] if np.any(sl != 0) else sl.ravel()
                slice_stats.append({
                    "slice": i + 1,
                    "mean": round(float(np.mean(sl_vals)), 2),
                    "std": round(float(np.std(sl_vals)), 2),
                    "min": round(float(np.min(sl_vals)), 2),
                    "max": round(float(np.max(sl_vals)), 2),
                })

            result["slice_statistics_sample"] = slice_stats

            all_valid = data[np.isfinite(data)]
            if len(all_valid) > 0:
                result["global_statistics"] = {
                    "mean": round(float(np.mean(all_valid)), 2),
                    "std": round(float(np.std(all_valid)), 2),
                    "min": round(float(np.min(all_valid)), 2),
                    "max": round(float(np.max(all_valid)), 2),
                }

            result["mrc_header_min_max_mean"] = {
                "dmin": float(header.dmin),
                "dmax": float(header.dmax),
                "dmean": float(header.dmean),
            }
    except Exception as e:
        result["error"] = str(e)

    return result


def _read_mrc_via_open(path: Path) -> dict:
    """Fallback: read MRC header without mmap (loads only header, not data)."""
    try:
        import mrcfile
    except ImportError:
        return {"error": "mrcfile library not available"}

    result = {"file": str(path.name), "file_size_mb": round(path.stat().st_size / (1024 * 1024), 1)}

    try:
        with mrcfile.open(str(path), permissive=True, mode='r', header_only=True) as mrc:
            header = mrc.header
            result["dimensions"] = {
                "nx": int(header.nx),
                "ny": int(header.ny),
                "nz": int(header.nz),
            }
            result["pixel_size"] = {
                "x_a": float(header.cella.x / header.nx) if header.nx > 0 else 0,
                "y_a": float(header.cella.y / header.ny) if header.ny > 0 else 0,
            } if header.cella.x > 0 else None
            result["data_type"] = int(header.mode)
            result["mrc_header_min_max_mean"] = {
                "dmin": float(header.dmin),
                "dmax": float(header.dmax),
                "dmean": float(header.dmean),
            }
            result["note"] = "Header only (mmap unavailable on this filesystem)"
    except Exception as e:
        result["error"] = str(e)

    return result


def _read_com_file(path: Path) -> dict:
    """Read an IMOD .com command file and extract key parameters."""
    content = path.read_text()
    result = {"file": str(path.name)}

    # Extract binning
    bin_match = re.search(r'-bin\w*\s+(\d+)', content, re.IGNORECASE)
    if bin_match:
        result["binning"] = int(bin_match.group(1))

    # Extract thickness
    thickness_match = re.search(r'-thick\w*\s+(\d+)', content, re.IGNORECASE)
    if thickness_match:
        result["thickness_pixels"] = int(thickness_match.group(1))

    # Extract radial filter
    radial_match = re.search(r'-Radial\s+([\d.]+)\s*,?\s*([\d.]+)', content)
    if radial_match:
        result["radial_filter"] = [float(radial_match.group(1)),
                                    float(radial_match.group(2))]

    # Check for anti-alias
    result["anti_alias"] = "antialias" in content.lower()

    # Check for GPU usage
    result["uses_gpu"] = "-gpu" in content.lower()

    return result


def _find_dataset_files(dataset_path: Path) -> dict:
    """Discover all relevant files in a cryo-ET dataset directory."""
    files = {
        "st_files": [str(p.relative_to(dataset_path))
                      for p in dataset_path.rglob("*.st")],
        "mrc_files": [str(p.relative_to(dataset_path))
                       for p in dataset_path.rglob("*.mrc")
                       if not p.name.endswith((".st", ".rawtlt"))],
        "tlt_files": [str(p.relative_to(dataset_path))
                       for p in dataset_path.rglob("*.tlt")],
        "rawtlt_files": [str(p.relative_to(dataset_path))
                          for p in dataset_path.rglob("*.rawtlt")],
        "xf_files": [str(p.relative_to(dataset_path))
                      for p in dataset_path.rglob("*.xf")],
        "com_files": [str(p.relative_to(dataset_path))
                       for p in dataset_path.rglob("*.com")],
        "ctf_files": [str(p.relative_to(dataset_path))
                       for p in dataset_path.rglob("*ctffind*.txt")],
    }
    return files


def _overall_assessment(tilt: dict | None, mrc: dict | None,
                         xf: dict | None, ctf: dict | None) -> dict:
    """Generate an overall dataset quality assessment."""
    grades = []

    if tilt:
        if tilt["tilt_range"] >= 100:
            grades.append({"dimension": "tilt_coverage", "grade": "excellent",
                           "note": f"Tilt range {tilt['tilt_range']}° covers >100°"})
        elif tilt["tilt_range"] >= 80:
            grades.append({"dimension": "tilt_coverage", "grade": "good",
                           "note": f"Tilt range {tilt['tilt_range']}°"})
        elif tilt["tilt_range"] >= 50:
            grades.append({"dimension": "tilt_coverage", "grade": "adequate",
                           "note": f"Tilt range {tilt['tilt_range']}°"})
        else:
            grades.append({"dimension": "tilt_coverage", "grade": "poor",
                           "note": f"Tilt range only {tilt['tilt_range']}°"})

        if tilt["missing_tilts"]["gaps_count"] > 0:
            grades.append({"dimension": "tilt_completeness", "grade": "warning",
                           "note": f"{tilt['missing_tilts']['gaps_count']} gap(s) in tilt series"})

    if xf and "drift_analysis" in xf:
        drift_assess = xf.get("assessment", "unknown")
        grades.append({"dimension": "alignment_drift", "grade": drift_assess,
                       "note": f"Cumulative drift {xf['drift_analysis']['cumulative_drift_pixels']} px"})

    if ctf and "ctf_quality" in ctf:
        ctf_assess = ctf.get("assessment", "unknown")
        grades.append({"dimension": "ctf_quality", "grade": ctf_assess,
                       "note": f"Mean score {ctf['ctf_quality'].get('mean_score', 'N/A')}"})

    if mrc and "error" not in mrc:
        dims = mrc.get("dimensions", {})
        grades.append({"dimension": "data_format", "grade": "valid",
                       "note": f"MRC stack {dims.get('nx', '?')}x{dims.get('ny', '?')}x{dims.get('nz', '?')}"})

    return {"grades": grades}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_dataset(dataset_path: str) -> str:
    """
    Assess the quality of a cryo-ET dataset.

    Reads tilt angles, MRC stack statistics, alignment transformations,
    and CTF output if available, then generates a comprehensive quality report.

    Args:
        dataset_path: Path to the dataset directory containing .st/.mrc,
                      .tlt/.rawtlt, .xf, and optional CTF output files.

    Returns:
        A formatted quality assessment report.
    """
    try:
        dp = _safe_path(dataset_path)
        if not dp.exists():
            return f"Error: Dataset path not found: {dataset_path}"
        if dp.is_file():
            return f"Error: Expected a directory, got a file: {dataset_path}"
    except ValueError as e:
        return f"Error: {e}"

    discovered = _find_dataset_files(dp)

    if not any(discovered.values()):
        return (f"No cryo-ET dataset files found in: {dataset_path}\n"
                f"Expected file types: .st, .mrc, .tlt, .rawtlt, .xf, .com, *ctffind*.txt")

    report_parts = [f"# Cryo-ET Dataset Quality Assessment\n"
                    f"**Dataset**: `{dataset_path}`\n"]

    # --- File Inventory ---
    report_parts.append("## 1. File Inventory\n")
    for ftype, file_list in discovered.items():
        if file_list:
            report_parts.append(f"- **{ftype}**: {len(file_list)} file(s)")
            for f in file_list[:5]:
                report_parts.append(f"  - `{f}`")
            if len(file_list) > 5:
                report_parts.append(f"  - ... and {len(file_list) - 5} more")
    report_parts.append("")

    # --- Tilt Angle Analysis ---
    report_parts.append("## 2. Tilt Angle Analysis\n")
    tilt_data = None
    tlt_file = None
    # Prefer .tlt (refined) over .rawtlt (raw)
    for suffix in ["*.tlt", "*.rawtlt"]:
        tlt_file = _find_file(dp, suffix)
        if tlt_file:
            break

    if tlt_file:
        tilt_data = _read_tlt_file(tlt_file)
        t = tilt_data
        report_parts.append(f"- **File**: `{t['file']}`")
        report_parts.append(f"- **Number of tilts**: {t['count']}")
        report_parts.append(f"- **Tilt range**: {t['min_angle']}° to {t['max_angle']}° (span: {t['tilt_range']}°)")
        report_parts.append(f"- **Median step**: {t['median_step']}°")
        report_parts.append(f"- **Step uniformity**: {'Uniform' if t['step_consistency']['is_uniform'] else 'Non-uniform'} "
                            f"(max deviation: {t['step_consistency']['max_deviation']}°)")
        report_parts.append(f"- **Acquisition scheme**: {t['dose_symmetric']['scheme']}")

        if t['missing_tilts']['gaps_count'] > 0:
            report_parts.append(f"- **WARNING**: {t['missing_tilts']['gaps_count']} gap(s) detected at positions: "
                                f"{t['missing_tilts']['gap_positions']}")
        else:
            report_parts.append(f"- **Missing tilts**: None detected")

        report_parts.append(f"- **Largest angular gap**: {t['largest_gap']['size_degrees']}° "
                            f"between {t['largest_gap']['between']}")
    else:
        report_parts.append("No .tlt or .rawtlt file found. Tilt angle analysis skipped.\n")
    report_parts.append("")

    # --- MRC Stack Analysis ---
    report_parts.append("## 3. MRC Stack Analysis\n")
    mrc_data = None
    st_file = _find_file(dp, "*.st", "*.mrc")
    if st_file:
        mrc_data = _read_mrc_header(st_file)
        if "error" in mrc_data:
            report_parts.append(f"**Error reading MRC**: {mrc_data['error']}\n")
        else:
            m = mrc_data
            report_parts.append(f"- **File**: `{m['file']}` ({m['file_size_mb']} MB)")
            dims = m.get("dimensions", {})
            report_parts.append(f"- **Dimensions**: {dims.get('nx')} × {dims.get('ny')} × {dims.get('nz')} "
                                f"(X × Y × tilts)")
            if m.get("pixel_size"):
                ps = m["pixel_size"]
                report_parts.append(f"- **Pixel size**: {ps['x_a']:.3f} × {ps['y_a']:.3f} Å")

            gs = m.get("global_statistics")
            if gs:
                report_parts.append(f"- **Global statistics**: mean={gs['mean']}, std={gs['std']}, "
                                    f"min={gs['min']}, max={gs['max']}")

            slices = m.get("slice_statistics_sample", [])
            if slices:
                report_parts.append(f"\n### Per-Slice Statistics (sample of {len(slices)} slices)\n")
                report_parts.append("| Slice | Mean | Std | Min | Max |")
                report_parts.append("|-------|------|-----|-----|-----|")
                for s in slices:
                    report_parts.append(f"| {s['slice']} | {s['mean']} | {s['std']} | {s['min']} | {s['max']} |")

                # Detect anomalous slices (std dev far from median)
                stds = np.array([s['std'] for s in slices])
                median_std = np.median(stds)
                anomalies = [s for s in slices if s['std'] > 3 * median_std]
                if anomalies:
                    report_parts.append(f"\n**WARNING**: {len(anomalies)} slice(s) have unusually high std: "
                                        f"{[a['slice'] for a in anomalies]}")
    else:
        report_parts.append("No .st or .mrc file found. MRC analysis skipped.\n")
    report_parts.append("")

    # --- Alignment Quality ---
    report_parts.append("## 4. Alignment Quality (XF Analysis)\n")
    xf_data = None
    xf_file = _find_file(dp, "*.xf")
    if xf_file:
        xf_data = _read_xf_file(xf_file)
        x = xf_data
        d = x["drift_analysis"]
        report_parts.append(f"- **File**: `{x['file']}` ({x['num_transforms']} transforms)")
        report_parts.append(f"- **Cumulative drift**: {d['cumulative_drift_pixels']} pixels")
        report_parts.append(f"- **Per-step drift (mean/max)**: {d['mean_per_step_drift']} / "
                            f"{d['max_per_step_drift']} pixels")
        report_parts.append(f"- **Total translation range**: X=[{d['total_x_range']}], Y=[{d['total_y_range']}] pixels")
        report_parts.append(f"- **Assessment**: {x['assessment'].replace('_', ' ').title()}")
    else:
        report_parts.append("No .xf file found. Alignment analysis skipped.\n")
    report_parts.append("")

    # --- CTF Quality ---
    report_parts.append("## 5. CTF Estimation Quality\n")
    ctf_data = None
    ctf_file = _find_file(dp, "*ctffind*.txt")
    if ctf_file:
        ctf_data = _read_ctf_file(ctf_file)
        c = ctf_data
        report_parts.append(f"- **File**: `{c['file']}` ({c.get('tilts_with_ctf', 0)} tilts)")

        if "defocus" in c:
            df = c["defocus"]
            report_parts.append(f"- **Defocus range**: {df['defocus_range_a'][0]:.0f} – "
                                f"{df['defocus_range_a'][1]:.0f} Å")
            report_parts.append(f"- **Mean defocus**: {df['mean_defocus1_a']:.0f} / {df['mean_defocus2_a']:.0f} Å")
            report_parts.append(f"- **Mean astigmatism**: {df['mean_astigmatism_a']:.1f} Å")

        if "ctf_quality" in c:
            q = c["ctf_quality"]
            report_parts.append(f"- **Quality scores**: mean={q['mean_score']}, min={q['min_score']}, "
                                f"max={q['max_score']}")
            if q['low_quality_tilts'] > 0:
                report_parts.append(f"- **WARNING**: {q['low_quality_tilts']} tilt(s) with low CTF quality")
            else:
                report_parts.append(f"- **Low-quality tilts**: None")

        report_parts.append(f"- **Overall CTF assessment**: {c.get('assessment', 'unknown').replace('_', ' ').title()}")
    else:
        report_parts.append("No CTF output file found. CTF analysis skipped.\n")
    report_parts.append("")

    # --- COM file parameters ---
    com_file = _find_file(dp, "*.com")
    if com_file:
        com_data = _read_com_file(com_file)
        report_parts.append("## 6. Reconstruction Parameters (from .com)\n")
        for k, v in com_data.items():
            if k != "file":
                report_parts.append(f"- **{k}**: {v}")
        report_parts.append("")

    # --- Overall Assessment ---
    report_parts.append("## 7. Overall Assessment\n")
    overall = _overall_assessment(tilt_data, mrc_data, xf_data, ctf_data)
    for g in overall["grades"]:
        icon = {"excellent": "[PASS]", "good": "[PASS]", "adequate": "[OK]",
                "warning": "[WARN]", "moderate": "[WARN]", "poor": "[FAIL]",
                "high_drift": "[WARN]", "valid": "[PASS]"}.get(g["grade"], "[INFO]")
        report_parts.append(f"- {icon} **{g['dimension']}** ({g['grade']}): {g['note']}")

    return "\n".join(report_parts)


def inspect_mrc(file_path: str, num_slices: int = 5) -> str:
    """
    Inspect a single MRC/ST file and return detailed header + slice statistics.

    Args:
        file_path: Path to a .mrc or .st file.
        num_slices: Number of evenly-spaced slices to sample for statistics.

    Returns:
        Formatted MRC inspection report.
    """
    try:
        fp = _safe_path(file_path)
        if not fp.exists():
            return f"Error: File not found: {file_path}"
        if fp.is_dir():
            return f"Error: Expected a file, got a directory: {file_path}"
    except ValueError as e:
        return f"Error: {e}"

    try:
        import mrcfile
    except ImportError:
        return "Error: mrcfile library not available."

    try:
        with mrcfile.mmap(str(fp), permissive=True, mode='r') as mrc:
            header = mrc.header
            data = mrc.data

            lines = [
                f"# MRC File Inspection: `{fp.name}`",
                f"",
                f"## Header",
                f"- **Dimensions (NX, NY, NZ)**: {header.nx}, {header.ny}, {header.nz}",
                f"- **Data type (mode)**: {header.mode}",
                f"- **Cell dimensions (Å)**: {header.cella.x:.1f}, {header.cella.y:.1f}, {header.cella.z:.1f}",
                f"- **Cell angles**: {header.cellb.x:.1f}, {header.cellb.y:.1f}, {header.cellb.z:.1f}",
                f"- **dmin/dmax/dmean**: {header.dmin:.2f}, {header.dmax:.2f}, {header.dmean:.2f}",
                f"- **File size**: {fp.stat().st_size / (1024**2):.1f} MB",
                f"",
                f"## Slice Statistics",
            ]

            nz = int(header.nz)
            step = max(1, nz // num_slices) if nz > num_slices else 1
            sampled = list(range(0, nz, step))[:num_slices]

            lines.append(f"| Slice | Mean | Std | Min | Max | Zero % |")
            lines.append(f"|-------|------|-----|-----|-----|--------|")
            for i in sampled:
                sl = data[i]
                sl_valid = sl[np.isfinite(sl)]
                zero_pct = np.sum(sl_valid == 0) / max(len(sl_valid), 1) * 100
                lines.append(f"| {i+1}/{nz} | {np.mean(sl_valid):.2f} | {np.std(sl_valid):.2f} | "
                             f"{np.min(sl_valid):.2f} | {np.max(sl_valid):.2f} | {zero_pct:.1f}% |")

            return "\n".join(lines)
    except Exception as e:
        return f"Error reading MRC file: {e}"
