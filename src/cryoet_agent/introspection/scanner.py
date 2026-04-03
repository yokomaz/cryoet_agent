from __future__ import annotations

from collections import Counter
from pathlib import Path

from cryoet_agent.agent.schemas import DatasetAsset, DatasetState
from cryoet_agent.config import IGNORED_DIRS, SCAN_LIMIT, workspace_root


EXTENSION_MAP = {
    ".eer": ("raw_movie", 0.98),
    ".tif": ("raw_movie", 0.80),
    ".tiff": ("raw_movie", 0.80),
    ".mdoc": ("metadata", 0.98),
    ".xml": ("metadata", 0.60),
    ".star": ("metadata", 0.75),
    ".mrc": ("unknown", 0.60),
    ".rec": ("tomogram", 0.90),
    ".coords": ("particle_coordinates", 0.90),
    ".txt": ("unknown", 0.20),
}

RAW_HINTS = ("movie", "frames", "fraction")
TILT_HINTS = ("tilt", "ts", "series")
ALIGN_HINTS = ("aligned", "xf", "ali")
TOMO_HINTS = ("tomo", "tomogram", "recon", "rec")
COORD_HINTS = ("coord", "particle", "pick")


def _safe_path(path: str) -> Path:
    root = workspace_root().resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {path}")
    return candidate


def _classify_path(file_path: Path) -> tuple[str, float]:
    suffix = file_path.suffix.lower()
    asset_type, confidence = EXTENSION_MAP.get(suffix, ("unknown", 0.15))
    lowered = file_path.name.lower()
    is_metadata = suffix in {".mdoc", ".xml", ".star"}

    if suffix == ".mrc":
        if any(token in lowered for token in TOMO_HINTS):
            return "tomogram", 0.92
        if any(token in lowered for token in ALIGN_HINTS):
            return "aligned_tilt_series", 0.80
        if any(token in lowered for token in TILT_HINTS):
            return "tilt_series", 0.75
        if any(token in lowered for token in RAW_HINTS):
            return "raw_movie", 0.55
    if any(token in lowered for token in COORD_HINTS):
        return "particle_coordinates", max(confidence, 0.75)
    if asset_type == "raw_movie":
        return asset_type, confidence
    if not is_metadata and any(token in lowered for token in TOMO_HINTS):
        return "tomogram", max(confidence, 0.70)
    if not is_metadata and any(token in lowered for token in TILT_HINTS):
        return "tilt_series", max(confidence, 0.65)
    return asset_type, confidence


def scan_workspace(dataset_path: str = ".") -> DatasetState:
    root = workspace_root().resolve()
    scan_root = _safe_path(dataset_path)
    state = DatasetState(workspace=str(root), requested_path=str(scan_root.relative_to(root)))

    if not scan_root.exists():
        state.warnings.append(f"Dataset path does not exist: {dataset_path}")
        return state

    if scan_root.is_file():
        asset_type, confidence = _classify_path(scan_root)
        state.assets.append(
            DatasetAsset(
                path=str(scan_root.relative_to(root)),
                asset_type=asset_type,
                confidence=confidence,
            )
        )
        _finalize_state(state)
        return state

    file_count = 0
    for path in sorted(scan_root.rglob("*")):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        file_count += 1
        if file_count > SCAN_LIMIT:
            state.warnings.append(
                f"Scan truncated after {SCAN_LIMIT} files. Narrow the dataset path if needed."
            )
            break

        asset_type, confidence = _classify_path(path)
        metadata = {"suffix": path.suffix.lower(), "size_bytes": path.stat().st_size}
        state.assets.append(
            DatasetAsset(
                path=str(path.relative_to(root)),
                asset_type=asset_type,
                confidence=confidence,
                metadata=metadata,
            )
        )

    _finalize_state(state)
    return state


def _finalize_state(state: DatasetState) -> None:
    counts = Counter(asset.asset_type for asset in state.assets)
    state.detected_modalities = sorted(k for k, v in counts.items() if v > 0 and k != "unknown")

    if counts["raw_movie"]:
        state.inferred_stage = "raw_tilt_movies"
    elif counts["tilt_series"] or counts["aligned_tilt_series"]:
        state.inferred_stage = "tilt_series"
    elif counts["tomogram"]:
        state.inferred_stage = "tomogram_ready"
    elif counts["particle_coordinates"]:
        state.inferred_stage = "particle_coordinates_present"

    if counts["raw_movie"] and not counts["metadata"]:
        state.missing_requirements.append(
            "No metadata file such as .mdoc, .star, or microscope export was detected."
        )
    if (counts["tilt_series"] or counts["aligned_tilt_series"]) and not counts["metadata"]:
        state.missing_requirements.append(
            "Tilt series detected without obvious tilt-angle metadata."
        )
    if counts["tomogram"] and not counts["particle_coordinates"]:
        state.notes.append("Tomograms detected but no particle coordinate file was found.")
    if not state.assets:
        state.warnings.append("No files were detected in the requested dataset path.")
