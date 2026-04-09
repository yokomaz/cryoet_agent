# CryoET-Agent

## Overview

CryoET-Agent is a **data-centric planning assistant** designed to bridge the gap between **cryo-electron tomography (cryo-ET)** workflows and **AI-driven research**.

Instead of requiring users to understand complex cryo-ET processing pipelines, CryoET-Agent helps them:

> **Reproduce training-ready data (e.g., subtomograms, particles) from raw datasets using paper-guided workflows.**

---

## Motivation

In cryo-ET, data is not directly usable.

Unlike standard computer vision datasets, cryo-ET data requires multiple preprocessing steps:

```
raw frames → motion correction → alignment → reconstruction → tomogram → particle picking → subtomograms
```

For researchers in machine learning:

* ❌ Tools are unfamiliar (Warp, IMOD, AreTomo, RELION, etc.)
* ❌ Pipelines are complex and poorly documented
* ❌ Papers describe methods but not executable workflows
* ❌ Data formats vary across datasets

As a result:

> Many AI researchers struggle not with modeling, but with **obtaining usable data**.

---

## What This Project Solves

CryoET-Agent focuses on a critical problem:

> **How to go from raw cryo-ET data to the same level of processed data used in published papers.**

Given:

* 📁 A raw dataset (local folder)
* 📄 A paper (methods section or PDF)
* 📌 Optional metadata (e.g., particle coordinates)

The agent will:

1. **Parse the paper workflow**
2. **Infer the target data representation** (e.g., subtomograms)
3. **Analyze the current dataset state**
4. **Align the workflow with available data**
5. **Generate a minimal reproducible pipeline with parameters for each tool**

---

## Key Idea

> ❗ The goal is NOT to reproduce the full pipeline
> ✅ The goal is to reproduce the **final data condition**

This means:

* Skip unnecessary steps
* Reuse available intermediate data
* Focus only on what is required to obtain usable training data

---

## Example Use Case

### Input

User provides:

* A path to raw dataset
* The description of the data processing pipeline in paper, which can be found in data processing section of a paper, such as:
```
Frames were motion corrected using Warp.
Tilt series were aligned and reconstructed using AreTomo.
Particles were picked and subtomograms extracted.
```
* The goal of users, it could be generate particle subtomograms for particle analysis, or tilt series for denoising, tomograms for missing wedge composition, etc.

---

### Output

CryoET-Agent generates:

```
🎯 Target: Subtomograms for particle analysis

📦 Current data:
- Raw frames detected
- No tomogram found
- Particle coordinates available

---

✅ Minimal workflow:

Step 1: Motion correction
Tool: Warp [parameters]

Step 2: Alignment + Reconstruction
Tool: AreTomo [parameters]

Step 3: Subtomogram extraction
Tool: Dynamo / Warp [parameters]

---

💡 Notes:
- Particle picking is skipped (coordinates already provided)
- Ensure tilt angles (.mdoc or .tlt) are available
```

---

## Core Features

### 1. Paper-Guided Workflow Extraction

* Converts natural language methods into structured pipelines
* Identifies tools, steps, and data dependencies

### 2. Dataset Awareness

* Scans local workspace
* Infers data type and processing stage
* Detects missing requirements

### 3. Workflow Alignment

* Adapts paper workflows to the user’s data
* Skips completed steps
* Fills missing steps

### 4. Minimal Pipeline Generation

* Produces only necessary steps
* Avoids redundant processing
* Optimized for AI data preparation

---

## System Design

CryoET-Agent follows a modular architecture:

```
User Input (Goal + Paper + Data)
        ↓
[Workspace Inspector] → dataset state
        ↓
[Paper Parser] → workflow graph
        ↓
[Workflow Aligner] → adapted pipeline
        ↓
[Planner] → structured output
```

---

## Design Philosophy

* **Data-first, not tool-first**
* **Reproduce results, not processes**
* **Minimize user burden**
* **Stay explainable and transparent**

---

## Target Users

* Machine learning researchers working with cryo-ET data
* Students unfamiliar with cryo-ET software ecosystem
* Researchers reproducing published results

---

## Roadmap

### Version 1

* Local CLI agent
* Paper-based workflow extraction
* Dataset-aware planning
* No tool execution (planning only)

### Version 2

* Tool command generation
* Parameter suggestion
* Optional cloud model support

### Version 3

* Automated execution with user approval
* Workflow optimization and tool selection
* Integration with cryo-ET software environments

---

## Why This Matters

CryoET-Agent lowers the barrier between:

* **Structural biology workflows**
* **AI-driven analysis**

By making data preparation accessible, it enables:

> Faster iteration, easier reproducibility, and broader adoption of AI in cryo-ET.

---

## License

MIT License
