# Changelog

## [0.3.0] — 2026-05-21

### Added
- **Coordinate System Transformation skill** (`skills/coordinate_system/`)
  - IMOD coordinate system as canonical reference
  - Per-tool reference docs: IMOD, AreTomo, Warp, RELION-tomo
  - Source code analysis patterns for detecting coordinate conventions
  - Scripts: `convert_tomogram.py`, `detect_coordinate_system.py`, `validate_coordinate_system.py`

- **Tool Availability Check skill** (`skills/tool_check/`)
  - Database of 25+ cryo-ET tools with binary names, install paths, env vars
  - 8 detection methods: PATH binary, known paths, env vars, Python import, MATLAB, conda, Docker, Singularity
  - Script: `check_tools.py` with JSON output for agent consumption

- **Dataset Quality Assessment tool** (`tools/dataset_quality.py`)
  - `assess_dataset`: tilt coverage, MRC statistics, alignment drift, CTF quality
  - `inspect_mrc`: MRC header + per-slice statistics

- **System Prompt** now includes 6-step workflow (extract → check tools → handle missing → coordinate check → plan)
- **Response Style** constraints for concise agent output

### Changed
- `TOOLS.py`: added `assess_dataset`, `inspect_mrc`, `read_file` tool definitions
- `PROMPT.py`: redesigned SYSTEM_PROMPT with full planning workflow; updated SUBAGENT_PROMPT to require tool names per step
- Motion Correction SKILL.md: expanded with cryo-ET specific parameters, tool comparison, decision flow
- `cli.py`: minor updates

---

## [0.2.0] — 2026-05-20

### Added
- Todo list tools (`add_task`, `start_task`, `complete_task`, `list_tasks`, `get_next_task`, `get_progress`, `fail_task`, `get_task_details`, `clear_completed_tasks`)
- Skill loader with SkillRegistry (auto-discovers `SKILL.md` files in `skills/`)
- `read_file` tool for reading file content with line limit
- Prompt updates for todo list and skill usage

### Changed
- Removed `safe_path`; path validation simplified
- Updated CLI to auto-print todo list status after operations

---

## [0.1.0] — 2026-04-14

### Added
- Initial project scaffold
- Interactive CLI agent with OpenAI-compatible API
- Agent loop with tool calling support
- `run_shell` tool with safety checks
- `pdf_parser` tool using pypdf
- `run_subagent` for isolated PDF workflow extraction
- Motion Correction skill (initial version)
- PDF Parser skill
- System prompt with basic cryo-ET workflow guidance
- `pip install -e .` package setup
