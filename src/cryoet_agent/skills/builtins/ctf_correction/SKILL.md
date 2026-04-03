---
name: ctf_correction
description: CTF correction planning skill for metadata-aware CryoET preprocessing workflows.
kind: task
stage: preprocessing
accepts:
  - raw_movie
  - tilt_series
requires:
  - tilt_angles
  - defocus_estimates
produces:
  - ctf_corrected_tilt_series
keywords:
  - ctf
  - defocus
priority_for:
  - ctf_correction
---
# CTF Correction

Use this skill when the user wants to estimate or correct CTF during CryoET preprocessing.

Important beginner guidance:

- Review fit quality instead of trusting every tilt equally.
- Keep the plan conditional if defocus estimation inputs are incomplete.

