---
name: imod
description: IMOD skill for manual inspection, tilt-series alignment, and tomographic reconstruction.
kind: tool
stage: alignment_reconstruction
accepts:
  - tilt_series
requires:
  - tilt_angles
  - pixel_size
produces:
  - aligned_tilt_series
  - tomogram
keywords:
  - imod
  - etomo
  - reconstruction
priority_for:
  - reconstruct_tomogram
---
# IMOD

IMOD is a strong option when the user needs more manual control and inspection during alignment and reconstruction.

Important beginner guidance:

- Prefer it when alignment diagnostics and manual correction matter more than full automation.
- Ask the user to review residuals and reconstructed slices before proceeding downstream.

