---
name: relion_sta
description: RELION-based subtomogram averaging skill for standardized refinement workflows.
kind: tool
stage: sta
accepts:
  - subtomogram_stack
requires:
  - particle_coordinates
produces:
  - classified_subtomograms
  - refined_average
keywords:
  - relion
  - sta
priority_for:
  - sta
---
# RELION STA

Use this skill when the user prefers a standardized subtomogram alignment and refinement path in RELION.

Important beginner guidance:

- Start with coarse angular sampling and limited class counts.
- Verify class plausibility before tightening refinement settings.

