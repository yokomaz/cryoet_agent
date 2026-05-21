---
name: Tool Availability Check
description: Detect whether specific cryo-ET/Cryo-EM data processing tools (IMOD, Warp, MotionCor3, AreTomo, CTFFIND4, RELION, novaCTF, emClarity, Dynamo, Gctf, crYOLO, pyTOM, deepEMhancer, Reliontomo, Topaz, cryoSPARC, etc.) are installed and available in the current environment. This skill is used when the agent has extracted a tool list from a paper's workflow and needs to verify local availability before generating a reproducible pipeline.
version: 1.0
---

# Tool Availability Check

## Overview

After extracting a data processing workflow from a paper, the agent must determine which tools the user has locally installed. This skill detects the presence of cryo-ET/Cryo-EM software tools in the user's environment.

A tool is considered **available** if it meets at least one of:
- CLI binary found in `$PATH`
- Known installation path exists (e.g., `/usr/local/IMOD`)
- Python package importable
- MATLAB toolbox detectable
- Environment variable pointing to installation

---

## Position in the Workflow

```
Paper PDF → [Subagent: Extract Workflow] → Tool List
                                               │
                                               ▼
                                    [This Skill: Check Tools]
                                               │
                                               ▼
                                    Availability Report
                                               │
                                               ▼
                                    Generate Pipeline Plan
                                    (map missing → alternatives)
```

This skill runs **after** workflow extraction and **before** pipeline generation. Its output determines whether the agent can follow the paper's tool chain directly or must suggest alternatives.

---

## Input

| Input | Required | Description |
|-------|----------|-------------|
| Tool names | Yes | List of tool names extracted from the paper workflow (e.g., `["Warp", "AreTomo", "IMOD"]`) |
| Paper context (optional) | No | The step each tool is used for, to help suggest appropriate alternatives if missing |

---

## Output

The script `scripts/check_tools.py` produces:

```json
{
  "tools": {
    "IMOD": {
      "status": "available",
      "method": "path_binary",
      "detail": "/usr/local/IMOD/bin/newstack",
      "version": "4.11.24"
    },
    "AreTomo": {
      "status": "missing",
      "method": null,
      "detail": "No binary found in PATH or known locations",
      "suggested_install": "https://github.com/czimaging/AreTomo"
    },
    "Warp": {
      "status": "available",
      "method": "path_binary",
      "detail": "/opt/WarpTools/bin/WarpTools",
      "version": null
    }
  },
  "summary": {
    "total": 3,
    "available": 2,
    "missing": 1,
    "uncheckable": 0
  },
  "missing_tools": ["AreTomo"],
  "action_required": "1 tool missing — alternatives or installation needed"
}
```

---

## Tool Database

The script maintains a database of known cryo-ET tools with their common binary names, check methods, typical install paths, and package identities. See `scripts/check_tools.py` for the full database.

### Tool Categories by Check Method

| Check Method | Examples | How It Works |
|-------------|----------|--------------|
| **`$PATH` binary** | IMOD, MotionCor3, ctffind4, Gctf, AreTomo | `shutil.which()` on known binary names |
| **Known install path** | IMOD (`/usr/local/IMOD`), RELION (`/usr/local/relion`) | Check directory existence |
| **Python package** | pyTOM, Topaz, cryoDRGN, Warp | `importlib.util.find_spec` |
| **MATLAB toolbox** | Dynamo, emClarity, TOM Toolbox | Check for `matlab` + known `.m` files |
| **Environment variable** | IMOD (`$IMOD_DIR`), RELION (`$RELION_DIR`) | Check env var existence |
| **Conda package** | cryoSPARC, RELION (conda installs) | `conda list` if conda available |
| **Docker/Singularity** | cryoSPARC, Warp Docker, RELION | `docker images` / `singularity` |

### Key Tools Database (excerpt)

| Tool | Binary Names | Install Paths | Type |
|------|-------------|---------------|------|
| **IMOD** | `etomo`, `newstack`, `tilt`, `3dmod` | `/usr/local/IMOD/bin`, `$IMOD_DIR/bin` | binary |
| **Warp** | `Warp`, `WarpTools`, `fs_motion_and_ctf` | `/opt/WarpTools`, `$WARP_HOME` | binary |
| **MotionCor3** | `MotionCor3`, `motioncor3` | `/usr/local/bin`, CUDA path | binary |
| **AreTomo** | `AreTomo`, `aretomo` | `/usr/local/bin`, `$ARETOMO_HOME` | binary |
| **CTFFIND4** | `ctffind`, `ctffind4` | `/usr/local/bin`, `$CISTEM_HOME` | binary |
| **Gctf** | `Gctf`, `gctf` | `/usr/local/bin` | binary |
| **RELION** | `relion`, `relion_refine` | `/usr/local/relion/bin`, `$RELION_HOME` | binary |
| **novaCTF** | `novaCTF`, `novactf` | `/usr/local/bin` | binary |
| **emClarity** | (MATLAB) | `$EMCLARITY_HOME` | matlab |
| **Dynamo** | (MATLAB) | `$DYNAMO_HOME` | matlab |
| **pyTOM** | `pytom` | pip install | python |
| **crYOLO** | `crYOLO`, `cryolo` | pip install, conda | python |
| **Topaz** | `topaz` | pip install, conda | python |
| **deepEMhancer** | `deepEMhancer` | pip install | python |
| **cryoSPARC** | `cryosparc` | `/opt/cryosparc`, `$CRYOSPARC_HOME` | binary |
| **RELION-tomo** | (included in RELION 5+) | `/usr/local/relion/bin` | binary |
| **IsoNet** | `isonet` | pip install | python |
| **cryoDRGN** | `cryodrgn` | pip install | python |
| **Sus scrofa** | `tomotwin` | pip install | python |

---

## Scripts

### `scripts/check_tools.py`

```bash
# Check specific tools extracted from a paper
python scripts/check_tools.py --tools Warp,AreTomo,IMOD,MotionCor3

# Check and output JSON for agent consumption
python scripts/check_tools.py --tools Warp,AreTomo --output report.json

# Check all known tools (system audit)
python scripts/check_tools.py --all

# Check including version info (slower)
python scripts/check_tools.py --tools IMOD,MotionCor3 --versions

# Quiet mode — only print missing tools
python scripts/check_tools.py --tools Warp,AreTomo --quiet
```

---

## Integration with Agent

### Typical Agent Flow

```
1. Agent extracts workflow from PDF via run_subagent:
   → ["MotionCor3", "IMOD", "Dynamo"]

2. Agent calls this skill's check script:
   → MotionCor3: available
   → IMOD: available
   → Dynamo: missing (no MATLAB detected)

3. Agent reads this SKILL.md for alternative suggestions:
   → Dynamo missing → suggest pyTOM or RELION particle picking

4. Agent generates pipeline plan with known-available tools,
   marking missing tools and suggesting alternatives
```

### How the Agent Should Use This Skill

1. Call `check_tools.py` with the tool list from the extracted workflow
2. Read the output report
3. For each missing tool, consult this SKILL.md's tool database for alternatives
4. Generate the final pipeline plan, marking which steps need alternatives

---

## Interpreting Results

### All Tools Available
```
✅ All N tools from the paper are installed.
No modifications needed — follow paper workflow directly.
```

### Some Tools Missing
```
⚠️  M tools missing (K/N available).
For missing tools:
  - <tool_A>: provide install instructions or suggest <alternative_A>
  - <tool_B>: suggest <alternative_B>
Mark these substitutions in the pipeline plan.
```

### Most Tools Missing
```
❌ Only K/N tools available.
This environment may not be ready for cryo-ET processing.
Suggest installing the core tools before proceeding:
  - IMOD (essential)
  - MotionCor3 or Warp (motion correction)
  - One reconstruction tool (AreTomo or IMOD)
```

---

## Tool Alternatives Quick Reference

When a tool from the paper is missing, consult the primary skill's reference documents for alternatives. General mapping:

| Missing Tool | Step | Primary Alternative | Secondary Alternative |
|-------------|------|-------------------|---------------------|
| **Warp** | Motion Correction | MotionCor3 | IMOD alignframes |
| **MotionCor3** | Motion Correction | Warp | IMOD alignframes |
| **AreTomo** | Alignment + Recon | IMOD (tiltxcorr + tilt) | RELION-tomo |
| **IMOD** | Various | (essential — install it) | (none) |
| **Dynamo** | Particle Picking / STA | pyTOM, RELION-tomo | crYOLO + custom extraction |
| **RELION** | STA | Dynamo | emClarity |
| **CTFFIND4** | CTF Estimation | Gctf | IMOD ctffind |
| **novaCTF** | 3D CTF Correction | Warp CTF | RELION-tomo CTF |
| **crYOLO** | Particle Picking | Dynamo vesicle models | template matching (pyTOM) |
| **deepEMhancer** | Denoising / Enhancement | cryoCARE | Topaz denoise |
| **IsoNet** | Missing-wedge recovery | (none direct) | deepEMhancer (partial) |

> **Note**: Alternatives produce different data states. Always document substitutions so downstream users are aware. For full details on each alternative, see the relevant skill reference documents.

---

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| Tool installed but not in `$PATH` | Reported as missing → unnecessary alternative | Check known install paths and env vars |
| MATLAB tools on headless server | `matlab` binary absent, but `.m` files exist | Check for `.m` files at known paths |
| Tool requires GPU but system has none | Installed binary, but runtime failure | Detect GPU before marking GPU tools as usable |
| WSL/Linux subsystem confusion | Windows paths don't translate | Linux-native tools preferred; warn on WSL |
| Conda env not activated | `which` can't find conda-installed tools | Check `$CONDA_PREFIX/bin` |
| Different versions of same tool | Old version lacks features used in paper | Use `--versions` flag and compare |
| Docker-only tools | `which` fails, but image exists | Check `docker images` and `singularity` |
