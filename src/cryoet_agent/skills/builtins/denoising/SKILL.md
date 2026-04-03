---
name: denoising
description: Denoising planning skill for tomogram interpretation workflows that preserve a raw reference volume.
kind: task
stage: postprocessing
accepts:
  - tomogram
requires:
  - tomogram
produces:
  - denoised_tomogram
keywords:
  - denoise
  - denoising
priority_for:
  - denoising
---
# Denoising

Use this skill when the user wants to denoise reconstructed tomograms.

Important beginner guidance:

- Always keep the raw tomogram alongside the denoised result.
- Treat denoising as an interpretation aid unless downstream validation supports stronger use.

