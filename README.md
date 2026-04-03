# cryoet-agent

`cryoet-agent` is a workspace-scoped CLI planner for beginner CryoET users.
It inspects the current project folder, loads CryoET skills on demand, and
returns a saved workflow plan for goals such as tomogram reconstruction,
denoising, particle picking, CTF correction, missing wedge compensation, and
subtomogram averaging.

Version 1 is planning-only:

- local-model ready, but no model download is performed here
- no execution of CryoET tools
- no access outside the current working directory
- markdown and JSON workflow export

## Intended workflow

```bash
cd /path/to/project
python -m venv .venv
source .venv/bin/activate
pip install -e .
cryoet-agent
```

Example request inside the interactive shell:

```text
I have dataset at ./data and I want to reconstruct tomograms and later do STA. Please give me a plan.
```

## Architecture

- `introspection/`: deterministic dataset scanning and asset classification
- `skills/`: CryoET knowledge base stored as loadable skills
- `agent/local_model.py`: Ollama-compatible local model adapter
- `agent/planner.py`: deterministic planning plus optional LLM refinement
- `planning/renderer.py`: markdown and JSON export

## Local model support

The code is prepared for a local model server such as Ollama, but it does not
download any model automatically. Set these environment variables later on the
target machine if you want LLM-assisted plan wording:

```bash
export CRYOET_AGENT_MODEL_PROVIDER=ollama
export CRYOET_AGENT_MODEL=qwen2.5:7b-instruct
export OLLAMA_HOST=http://127.0.0.1:11434
```

If no local model is configured or reachable, the agent falls back to the
built-in deterministic planner.
