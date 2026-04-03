---
name: aretomo
description: AreTomo alignment and tomogram reconstruction skill for beginner-friendly fiducial-less CryoET workflows.
kind: tool
stage: alignment_reconstruction
accepts:
  - tilt_series
  - aligned_tilt_series
requires:
  - tilt_angles
  - pixel_size
produces:
  - aligned_tilt_series
  - tomogram
keywords:
  - aretomo
  - alignment
  - reconstruct
priority_for:
  - reconstruct_tomogram
---
# AreTomo

AreTomo is often a practical beginner option for tilt-series alignment and tomogram reconstruction.

Important beginner guidance:

- Check tilt axis orientation before final reconstruction.
- Use a quick binned reconstruction for QC before final output.
- Keep reconstruction conditional if tilt-angle metadata is incomplete.

