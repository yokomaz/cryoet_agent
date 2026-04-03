from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MODEL_PROVIDER = os.getenv("CRYOET_AGENT_MODEL_PROVIDER", "none").strip().lower()
DEFAULT_MODEL_NAME = os.getenv("CRYOET_AGENT_MODEL", "qwen2.5:7b-instruct")
DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

PLAN_DIR_NAME = "plans"
SESSION_DIR_NAME = ".cryoet_agent"
SCAN_LIMIT = 2000
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    SESSION_DIR_NAME,
    PLAN_DIR_NAME,
}


def workspace_root() -> Path:
    return Path.cwd().resolve()

