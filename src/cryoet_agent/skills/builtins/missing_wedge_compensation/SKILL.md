---
name: missing_wedge_compensation
description: Missing-wedge compensation planning skill for downstream CryoET analysis and STA-aware interpretation.
kind: task
stage: analysis
accepts:
  - tomogram
requires:
  - tomogram
produces:
  - compensated_analysis_strategy
keywords:
  - missing wedge
priority_for:
  - missing_wedge_compensation
  - sta
---
# Missing Wedge Compensation

Use this skill when the user wants guidance on handling anisotropic angular sampling in tomograms or subtomograms.

Important beginner guidance:

- Missing wedge handling is often tied to downstream analysis rather than a single reconstruction flag.
- Encourage comparison between compensated and uncompensated outputs.

