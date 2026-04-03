---
name: warp
description: Warp preprocessing skill for motion correction, metadata association, and CTF estimation in CryoET.
kind: tool
stage: preprocessing
accepts:
  - raw_movie
  - tilt_series
requires:
  - detector_metadata
produces:
  - motion_corrected_tilt_series
  - ctf_estimates
keywords:
  - warp
  - motion correction
  - ctf
priority_for:
  - reconstruct_tomogram
  - ctf_correction
---
# Warp

Warp is a common preprocessing option for CryoET users starting from raw movies.

Use it for:

- motion correction
- tilt metadata association
- CTF estimation and review

Important beginner guidance:

- Verify gain, detector mode, and frame grouping before batch processing.
- Do not treat unstable high-tilt CTF fits as equally trustworthy as low-tilt fits.

