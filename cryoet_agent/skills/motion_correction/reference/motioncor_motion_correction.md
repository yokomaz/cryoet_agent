# MotionCor3 Reference

> **Version**: This reference is based on MotionCor3 >= 1.5.x. Some features (e.g., improved batch buffer pool) require v1.5.2+.

## Overview

MotionCor3 is a multi-GPU accelerated program for anisotropic beam-induced motion correction of cryo-EM and cryo-ET images. It is an improved implementation of MotionCor2 with integrated CTF (Contrast Transfer Function) estimation. MotionCor3 performs iterative, patch-based motion detection combined with spatial/temporal constraints and dose weighting.

## Prerequisites

### 1. Hardware
- Linux platform with at least one NVIDIA GPU
- CUDA toolkit installed

### 2. Input Data
- **Movie stacks** in one of the following formats:
  - MRC (`-InMrc`)
  - TIFF (`-InTiff`)
  - EER (`-InEer`)
- **Gain reference** (optional but recommended): MRC or TIFF file
- **Dark reference** (optional): MRC file
- **Defect file/map** (optional): for bad pixel correction

## Command Syntax

```bash
MotionCor3 -InMrc <input.mrc> -OutMrc <output.mrc> [options]
```

For serial (batch) processing of all files in a folder:
```bash
MotionCor3 -InMrc <folder/> -OutMrc <prefix> -Serial 1 [options]
```

---

## Input / Output Parameters

### Input Files

| Parameter | Description |
|-----------|-------------|
| `-InMrc <file/folder>` | Input MRC file or folder containing multiple MRC files |
| `-InTiff <file>` | Input TIFF file |
| `-InEer <file>` | Input EER file |
| `-InSuffix <suffix>` | When `-Serial 1`, only process files whose names contain this suffix |
| `-InSkips <string>` | Skip input files whose names contain the specified string(s) |
| `-InAln <folder>` | Load pre-calculated alignment files from this folder (bypasses alignment) |

### Output Files

| Parameter | Description |
|-----------|-------------|
| `-OutMrc <file>` | Output MRC file storing the frame sum |
| `-ArcDir <folder>` | Archive folder for 4-bit packed raw stacks |
| `-FullSum <file>` | Temporary MRC file for global-motion corrected, unweighted sum (useful for quick CTF check) |
| `-OutAln <folder>` | Save alignment files (settings + measured motion) to this folder |
| `-LogDir <folder>` | Directory for log files (named after output MRC with `.log` extension) |
| `-OutStack <flag> <binZ>` | Generate aligned stack. `flag`=1 enables it; `binZ`=frames to sum per output frame |
| `-OutStar <1/0>` | Generate a Relion-compatible STAR file for polishing. Default: 0 (disabled) |

### Reference Files

| Parameter | Description |
|-----------|-------------|
| `-Gain <file>` | Gain reference (MRC). If omitted, the MRC extended header is checked |
| `-Dark <file>` | Dark reference (MRC). Skipped if not provided |
| `-DefectFile <file>` | Text file with rectangular defect entries (`x y w h` per line) |
| `-DefectMap <file>` | Binary defect map (MRC mode 0 or 5 / TIFF). 1 = bad pixel, 0 = good |
| `-FmIntFile <file>` | Frame integration file (non-uniform grouping) |
| `-TmpFile <file>` | Temporary image file for debugging |

## Motion Correction Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-Patch <nx> <ny> [overlap%]` | int int [int] | 1 1 0 | Number of patches in X and Y for local motion correction. Overlap percentage is optional (0–100) |
| `-Iter <n>` | int | 15 | Maximum iterations for iterative alignment |
| `-Tol <px>` | float | 0.1 | Tolerance for iterative alignment (pixels) |
| `-Bft <global> [local]` | float [float] | 500 100 | B-factor for alignment. Two values: global and local (patch) alignment |
| `-PhaseOnly <0/1>` | int | 0 | Use only phase in cross-correlation |
| `-FtBin <factor>` | float | 1.0 | Fourier-space binning factor |
| `-Align <0/1>` | int | 1 | Generate motion-corrected sum (1) or simple sum (0) |
| `-FmRef <n>` | int | -1 | Reference frame (1-based). -1 = central frame |
| `-Group <global> <patch>` | int int | 1 4 | Group N frames before measuring shifts. 1st = global alignment, 2nd = patch alignment |
| `-Throw <n>` | int | 0 | Throw away first N frames |
| `-Trunc <n>` | int | 0 | Truncate last N frames |
| `-SumRange <min> <max>` | float float | 3.0 25.0 | Sum only frames whose accumulated dose falls in this range (e⁻/Å²) |
| `-Crop <x> <y>` | int int | 0 0 | Crop frames to the given size (must be even) |
| `-Mag <major> <minor> <angle>` | float float float | 1.0 1.0 0.0 | Anisotropic magnification correction (major scale, minor scale, major axis angle in degrees) |
| `-InFmMotion <0/1>` | int | 0 | Account for in-frame motion |
| `-CorrInterp <0/1>` | int | 0 | Enable interpolation compensation |
| `-SplitSum <0/1>` | int | 0 | Generate odd- and even-frame sums |
| `-TiffOrder <1/-1>` | int | 1 | Read TIFF frames forward (1) or backward (-1). Relevant for EER TIFF |

## Dose Weighting Parameters

Dose weighting is enabled only when `-FmDose`, `-PixSize`, and `-kV` are provided.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-InitDose <val>` | float | 0.0 | Initial dose received before stack acquisition (e⁻/Å²) |
| `-FmDose <val>` | float | 0.0 | Frame dose (e⁻/Å²). If 0, dose weighting is skipped |
| `-PixSize <val>` | float | 0.0 | Pixel size in Ångström. Required for dose weighting |
| `-kV <val>` | int | 300 | Acceleration voltage (kV) |

### Tilt Series Dose Weighting
| Parameter | Description |
|-----------|-------------|
| `-Tilt <start_angle> <step_angle>` | Required for tomographic stacks to compute initial dose at each tilt |

## CTF Estimation Parameters (MotionCor3 Integrated)

CTF estimation is enabled when `-Cs` is set to a non-zero value.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-Cs <val>` | float | 0.0 | Spherical aberration in mm. **Default 0 means NO CTF estimation** |
| `-AmpCont <val>` | float | 0.07 | Amplitude contrast |
| `-ExtPhase <val>` | float | 0.0 | Extra phase shift in degrees. If > 0, phase shift is estimated in a range centered at this value |

## GPU Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-Gpu <id1> [id2] ...` | int list | 0 | GPU device IDs to use. Multiple IDs can be space-separated |
| `-GpuMemUsage <fraction>` | float | 0.75 | Fraction of GPU memory used for frame buffering (range 0–0.8) |
| `-UseGpus <n>` | int | 0 | Number of free GPUs to use out of those listed in `-Gpu`. 0 = use all listed |

## EER Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-EerSampling <mode>` | int | 1 | EER rendering mode: 1 = default, 2 = 2×2, 3 = 4×4 supersampling |

## Gain Manipulation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-RotGain <0/1/2/3>` | int | 0 | Rotate gain counter-clockwise: 0=none, 1=90°, 2=180°, 3=270° |
| `-FlipGain <0/1/2>` | int | 0 | Flip gain after rotation: 0=none, 1=upside down, 2=left-right |
| `-InvGain <0/1>` | int | 0 | Inverse gain value (1/f) at each pixel |

**Note**: Rotation is applied first, then flipping.

## Typical Usage Examples

### Example 1: Basic single-stack motion correction with dose weighting
```bash
MotionCor3 \
  -InMrc movie.mrc \
  -OutMrc corrected.mrc \
  -Gain gain_ref.mrc \
  -PixSize 0.885 \
  -FmDose 1.2 \
  -kV 300 \
  -Patch 5 5 \
  -Gpu 0
```

### Example 2: Batch processing all MRC files in a folder
```bash
MotionCor3 \
  -InMrc /data/movies/ \
  -OutMrc /data/corrected/ \
  -Serial 1 \
  -InSuffix .mrc \
  -Gain gain_ref.mrc \
  -PixSize 0.885 \
  -FmDose 1.2 \
  -kV 300 \
  -Patch 5 5 \
  -Gpu 0 1 2 3
```

### Example 3: Motion correction + CTF estimation
```bash
MotionCor3 \
  -InMrc movie.mrc \
  -OutMrc corrected.mrc \
  -Gain gain_ref.mrc \
  -PixSize 0.885 \
  -FmDose 1.2 \
  -kV 300 \
  -Cs 2.7 \
  -AmpCont 0.07 \
  -Patch 5 5 \
  -Gpu 0
```

### Example 4: Generate aligned stack and split sums
```bash
MotionCor3 \
  -InMrc movie.mrc \
  -OutMrc corrected.mrc \
  -OutStack 1 1 \
  -SplitSum 1 \
  -Gain gain_ref.mrc \
  -PixSize 0.885 \
  -FmDose 1.2 \
  -kV 300 \
  -Gpu 0
```

### Example 5: Reload alignment to re-generate sums
```bash
MotionCor3 \
  -InMrc movie.mrc \
  -OutMrc recorrected.mrc \
  -InAln alignment_folder/ \
  -Gpu 0
```

### Example 6: cryo-ET tilt series with dose weighting + aligned stack
```bash
MotionCor3 \
  -InMrc /data/tilt_series/ \
  -OutMrc /data/corrected/ \
  -Serial 1 \
  -InSuffix .mrc \
  -Gain gain_ref.mrc \
  -PixSize 1.35 \
  -FmDose 0.05 \
  -InitDose 0.0 \
  -kV 300 \
  -Tilt -60 3 \
  -Patch 3 3 50 \
  -OutStack 1 1 \
  -SplitSum 1 \
  -Gpu 0 1 2 3
```
Note: `-Tilt -60 3` means the tilt series started at -60° with a 3° step. MotionCor3 uses this to compute per-tilt accumulated dose. `-FmDose 0.05` is the dose per frame in e⁻/Å².

### Example 7: cryo-ET tilt series with CTF estimation
```bash
MotionCor3 \
  -InMrc movie.mrc \
  -OutMrc corrected.mrc \
  -Gain gain_ref.mrc \
  -PixSize 1.35 \
  -FmDose 0.05 \
  -kV 300 \
  -Tilt -60 3 \
  -Cs 2.7 \
  -AmpCont 0.07 \
  -Patch 3 3 50 \
  -OutStack 1 1 \
  -Gpu 0
```

---

## cryo-ET Tilt Series Specifics

### Key Differences from Single-Particle cryo-EM

| Aspect | Single-Particle | cryo-ET Tilt Series |
|--------|----------------|---------------------|
| Dose per movie | Uniform (same dose per movie) | Varies per tilt (accumulated dose from prior tilts) |
| `-Tilt` parameter | Not used | **Required** for correct dose weighting |
| `-Patch` | `5 5` typical | `3 3` with higher overlap (50%) recommended |
| `-OutStack` | Optional | **Strongly recommended** (`-OutStack 1 1`) |
| `-SplitSum` | Optional | Recommended for denoiser training |
| EER | Rare | Common |

### How `-Tilt` Works

`-Tilt <start_angle> <step_angle>` tells MotionCor3 the acquisition geometry:
- `start_angle`: The first tilt angle in the series (e.g., `-60` means starting at -60°)
- `step_angle`: The angular step between consecutive tilts (e.g., `3` means 3° increments)

MotionCor3 uses this to compute each image's initial dose as:
```
initial_dose_per_tilt = -InitDose + (tilt_index) × (frames_per_tilt) × (-FmDose)
```

### cryo-ET Parameter Selection Guide

| Parameter | Recommended for cryo-ET | Rationale |
|-----------|------------------------|-----------|
| `-Patch` | `3 3 50` | Fewer patches + high overlap to avoid overfitting low-dose tilts |
| `-Bft` | `300 100` (less aggressive global B-factor) | Preserve signal at high tilt angles |
| `-Group` | `1 2` | Finer temporal sampling given few frames per tilt |
| `-FmDose` | Per-frame dose (typically 0.03–0.08 e⁻/Å²) | Enables dose weighting; critical for cryo-ET |
| `-Tilt` | Per acquisition geometry | Required for correct per-tilt dose accumulation |
| `-OutStack` | `1 1` | Preserves aligned stack for tomogram reconstruction |
| `-SplitSum` | `1` | Useful for downstream denoising |

## Output File Summary

| File | Description |
|------|-------------|
| `<output>.mrc` | Motion-corrected sum (dose-weighted if parameters provided) |
| `<output>_DW.mrc` | Dose-weighted sum (generated when dose weighting is enabled) |
| `<output>_odd.mrc` / `<output>_even.mrc` | Odd/even frame sums (if `-SplitSum 1`) |
| `<output>.log` | Processing log |
| `-FullSum` file | Temporary unweighted global-motion corrected sum |
| `-OutAln` folder | Text alignment files for re-processing |
| `-OutStar 1` | Relion 4 polishing STAR file |
| `-ArcDir` folder | 4-bit packed archived raw stacks |

## Troubleshooting Quick Reference

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| `No GPU found` or CUDA errors | CUDA not installed or wrong GPU IDs | Check `nvidia-smi` and use correct `-Gpu` IDs |
| Gain size mismatch | Gain dimensions do not match movie frames | Verify `-Gain` file matches camera dimensions and check `-RotGain`/`-FlipGain` |
| Dose weighting skipped | Missing `-FmDose`, `-PixSize`, or `-kV` | Provide all three parameters |
| CTF estimation skipped | `-Cs` is 0 or missing | Set `-Cs` to a non-zero value (e.g., 2.7) |
| Black output with `-Align 0` and `-SplitSum 1` | Known bug in older versions | Ensure you are using MotionCor3 >= 1.0.1 |
| Crash during batch processing of movies with different frame counts | Buffer pool size mismatch | Use MotionCor3 >= 1.5.2 or later |
