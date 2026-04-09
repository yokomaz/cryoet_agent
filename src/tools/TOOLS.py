from .shell import run_shell

# Wrapper to adapt run_shell's return value (ShellResult) to string
TOOL_HANDLERS = {
    "run_shell": lambda **kw: str(run_shell(kw["command"]))
}

TOOLS = [
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
