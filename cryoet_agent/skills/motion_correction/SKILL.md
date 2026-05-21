---
name: Motion Correction
description: Perform motion correction for frames data of Cryo-EM, Cryo-ET data. This skill is used when the agent plans a motion correction step in the cryo-ET data processing workflow.
version: 1.0
---

# Motion Correction

## Overview

Motion correction is the process of algorithmically correcting for motion of the electron microscope stage and the sample ice itself to recover image quality lost by motion blurring.

Cryo-EM and Cryo-ET data is collected in the form of movies, which are each a series of individual frames. Since a frame is usually between 0.1 and 0.2 seconds, the detector does not accumulate enough electron dose for clear identification of the target. However, the brief length of time significantly reduces the amount of in-frame motion blur.

## Position in the cryo-ET Pipeline

```
Raw Movie Frames → [Motion Correction] → CTF Estimation → Tilt Series Alignment → Tomogram Reconstruction
```

Motion correction is the **first processing step** after data collection. Its output (aligned averages or stacks) feeds directly into CTF estimation and tilt series alignment. Errors or artifacts introduced here propagate through the entire downstream pipeline.

## Input Data

Motion correction typically receives **raw movie frames** collected from the electron microscope. These frames can be in various formats:

| Format | Typical Usage |
|--------|--------------|
| TIFF | Common in older datasets, K2/K3 detectors |
| MRC | Widely used, flexible |
| EER | Increasingly common in cryo-ET for storage efficiency |
| TIF (stacked) | Single-file multi-frame stacks |

Additionally, a **gain reference file** is typically required for accurate flat-field correction. A **defect map** may be used to mask bad pixels.

### cryo-ET Specific Input Considerations

- Tilt series contain **multiple movies** (one per tilt angle), each with potentially different accumulated dose
- EER format is common in cryo-ET due to the large number of tilts
- The dose per frame/per tilt is typically lower than in single-particle cryo-EM

## Output Data

| Output | Description |
|--------|-------------|
| Motion-corrected average / sum | The primary output — a 2D image with corrected motion |
| Motion trajectories | Per-frame or per-patch X/Y shifts (stored in XML, STAR, or text files) |
| Aligned stack (optional) | Frame stack with motion correction applied; **required for cryo-ET** |
| Odd/even half-maps (optional) | Used for denoiser training or resolution estimation |
| Dose-weighted sum (optional) | Sum with per-frame dose weighting applied |

## Tool Selection

| Criteria | Warp | MotionCor3 |
|----------|------|------------|
| GPU utilization | Multi-GPU, decent scaling | Multi-GPU, excellent scaling |
| CTF estimation | Integrated (`fs_motion_and_ctf`) | Integrated (via `-Cs` parameter) |
| Real-time processing | Yes (designed for it) | No |
| GUI available | Yes | No (CLI only) |
| cryo-ET tilt series | Good — flexible grid model, low-dose friendly | Good — explicit `-Tilt` parameter for dose-per-tilt |
| EER support | Yes (`--eer_ngroups`) | Yes (`-InEer`, `-EerSampling`) |
| Learning curve | Moderate | Low (flat CLI) |

### Decision Flow

1. Need a GUI or real-time feedback? → **Warp**
2. Batch processing hundreds of movies on a cluster? → **MotionCor3**
3. cryo-ET tilt series with dose weighting per tilt? → Both work; **MotionCor3** has a simpler `-Tilt` interface; **Warp** handles it through the settings file
4. Want motion + CTF in a single command? → Both support it; **Warp** via `fs_motion_and_ctf`, **MotionCor3** via `-Cs`

## cryo-ET Key Parameters

When applying motion correction to cryo-ET tilt series, pay special attention to:

### Dose Weighting
Each tilt has a different accumulated dose (the initial dose depends on earlier tilts). Both tools support this:
- **MotionCor3**: Use `-Tilt <start_angle> <step_angle>` along with `-FmDose`, `-PixSize`, `-kV`
- **Warp**: Dose per tilt is derived from the total exposure set in the `.settings` file

### Grid / Patch Size
Since per-tilt dose is low in cryo-ET, use smaller models:
- **Warp**: `--grid 1x1x3` or `1x1x5` (fewer patches, fewer temporal bins)
- **MotionCor3**: `-Patch 3 3` (fewer patches; use higher overlap %)

### Preserve Aligned Stack
cryo-ET needs the aligned frame stack (not just the sum), because downstream tomogram reconstruction requires individual aligned frames:
- **MotionCor3**: `-OutStack 1 1`
- **Warp**: Output the per-frame alignment metadata (XML); the aligned stack is typically reconstructed by the tilt series alignment tool

### EER Frame Grouping
- **Warp**: `--eer_ngroups` in `create_settings`
- **MotionCor3**: `-EerSampling 1` (default)

## Tools

1. **Warp** — Software package for real-time processing of cryo-EM data, including motion correction. Detailed reference: `./reference/warp_motion_correction.md`
2. **MotionCor3** — Multi-GPU accelerated motion correction with integrated CTF estimation. Detailed reference: `./reference/motioncor_motion_correction.md`

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| Skipping dose weighting for tilt series | Incorrect per-frame weighting; high-noise tilts over-contribute | Always provide `-FmDose`, `-PixSize`, `-kV` (MotionCor3) or `--exposure` (Warp) |
| Using too large a patch grid for low-dose tilts | Noisy patch trajectories, overfitting | Use `Patch 3 3` (MotionCor3) or `--grid 1x1x3` (Warp) |
| Not preserving aligned stacks for cryo-ET | Cannot proceed to tomogram reconstruction | Use `-OutStack 1 1` (MotionCor3) or verify alignment metadata is saved (Warp) |
| Forgetting to provide a gain reference | Uncorrected detector artifacts | Always include `-Gain` or `--gain_path`
