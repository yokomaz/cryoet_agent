from .shell import run_shell
from .pdf_parser import pdf_parser_safe
from .run_subagent import run_subagent, SUBAGENT_TOOLS

# Wrapper to adapt return values to string for tool handlers
TOOL_HANDLERS = {
    "run_shell": lambda **kw: run_shell(kw["command"]),
    "pdf_parser": lambda **kw: pdf_parser_safe(kw["pdf_path"]),
    "run_subagent": lambda **kw: run_subagent(kw["prompt"])
}

# Base tools available to all agents
BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "A tool for executing shell commands safely. Returns the combined stdout and stderr output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

# Parent agent tools (includes run_subagent)
PARENT_TOOLS = BASE_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "run_subagent",
            "description": "Spawn a subagent with isolated context to extract a structured JSON workflow from a PDF file. The subagent will parse the PDF, analyze the data processing pipeline, and return a JSON-formatted workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt containing the PDF path and instructions for the subagent. The prompt should include the PDF file path and any specific instructions for the subagent to follow when extracting the workflow."
                    }
                },
                "required": ["prompt"]
            }
        }
    }
]
