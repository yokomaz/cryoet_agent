---
name: particle_picking
description: Particle-picking planning skill for finding candidate particles in tomograms before extraction.
kind: task
stage: picking
accepts:
  - tomogram
requires:
  - tomogram
produces:
  - particle_coordinates
keywords:
  - pick
  - particle
priority_for:
  - particle_picking
  - sta
---
# Particle Picking

Use this skill when the user wants to locate particles inside tomograms.

Important beginner guidance:

- Start with a conservative picking strategy that can be visually reviewed.
- Validate coordinates in orthoslices before large-scale extraction.

