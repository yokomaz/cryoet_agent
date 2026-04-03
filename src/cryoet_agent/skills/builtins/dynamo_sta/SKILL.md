---
name: dynamo_sta
description: Dynamo-based subtomogram averaging skill for flexible STA workflows and iterative curation.
kind: tool
stage: sta
accepts:
  - subtomogram_stack
requires:
  - particle_coordinates
produces:
  - aligned_subtomograms
  - refined_average
keywords:
  - dynamo
  - sta
priority_for:
  - sta
---
# Dynamo STA

Use this skill when the user prefers a flexible, iterative subtomogram workflow in Dynamo.

Important beginner guidance:

- Emphasize particle curation and mask design.
- Avoid aggressive refinement before the particle set is stable.

