---
name: reconstruct_tomogram
description: Plan beginner-safe CryoET workflows that turn raw tilt movies or tilt series into tomograms.
kind: task
stage: reconstruction
accepts:
  - raw_movie
  - tilt_series
  - aligned_tilt_series
requires:
  - tilt_angles
  - pixel_size
produces:
  - tomogram
keywords:
  - reconstruct
  - tomogram
  - reconstruction
priority_for:
  - reconstruct_tomogram
---
# Reconstruct Tomogram

Use this skill when the user wants to go from raw tilt movies or tilt series to a reconstructed tomogram.

Important beginner guidance:

- Confirm tilt-angle ordering before reconstruction.
- Prefer a quick binned reconstruction for quality control before high-resolution output.
- Keep the workflow conditional when metadata such as tilt angles or pixel size is missing.

