---
name: sta
description: Subtomogram averaging planning skill for CryoET workflows from tomogram to aligned subtomogram averages.
kind: task
stage: sta
accepts:
  - tomogram
  - particle_coordinates
requires:
  - tomogram
  - particle_coordinates
produces:
  - subtomogram_stack
  - subtomogram_average
keywords:
  - sta
  - subtomogram averaging
priority_for:
  - sta
---
# Subtomogram Averaging

Use this skill when the user wants to go from tomograms and particle coordinates to subtomogram refinement.

Important beginner guidance:

- Start with conservative extraction and coarse angular searches.
- Clean particle sets before pursuing high-resolution refinement.

