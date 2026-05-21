from .shell import run_shell
from .pdf_parser import pdf_parser_safe
from .run_subagent import run_subagent, SUBAGENT_TOOLS
from .read_file import read_file, safe_path
from .dataset_quality import assess_dataset, inspect_mrc
from . import todo_list
from cryoet_agent.skill_loader import SKILL_REGISTRY


def read_skill(skill_name: str) -> str:
    """
    Read the full content of a skill by name.
    
    Args:
        skill_name: The name of the skill to read (e.g., "Motion Correction")
        
    Returns:
        The full text content of the skill including its body content
    """
    return SKILL_REGISTRY.load_full_text(skill_name)


def list_skills() -> str:
    """
    List all available skills with their descriptions.
    
    Returns:
        A formatted list of available skills
    """
    return SKILL_REGISTRY.describe_available()


# Wrapper to adapt return values to string for tool handlers
TOOL_HANDLERS = {
    "run_shell": lambda **kw: run_shell(kw["command"]),
    "pdf_parser": lambda **kw: pdf_parser_safe(kw["pdf_path"]),
    "run_subagent": lambda **kw: run_subagent(kw["prompt"]),
    "read_skill": lambda **kw: read_skill(kw["skill_name"]),
    "list_skills": lambda **kw: list_skills(),
    "read_file": lambda **kw: read_file(kw["path"], kw.get("limit")),
    # Dataset quality tools
    "assess_dataset": lambda **kw: assess_dataset(kw["dataset_path"]),
    "inspect_mrc": lambda **kw: inspect_mrc(kw["file_path"], kw.get("num_slices", 5)),
    # Todo list tools
    "add_task": lambda **kw: todo_list.add_task(kw["description"], kw.get("notes", "")),
    "start_task": lambda **kw: todo_list.start_task(kw["task_id"]),
    "complete_task": lambda **kw: todo_list.complete_task(kw["task_id"], kw.get("notes", "")),
    "fail_task": lambda **kw: todo_list.fail_task(kw["task_id"], kw.get("reason", "")),
    "list_tasks": lambda **kw: todo_list.list_tasks(kw.get("status", "all")),
    "get_next_task": lambda **kw: todo_list.get_next_task(),
    "get_task_details": lambda **kw: todo_list.get_task_details(kw["task_id"]),
    "get_progress": lambda **kw: todo_list.get_progress(),
    "clear_completed_tasks": lambda **kw: todo_list.clear_completed_tasks(),
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file given its path. Returns the file content as a string. Use the 'limit' parameter to read only the first N lines of the file if it's too large.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to read (relative to the working directory)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional. If set, limits the number of lines read from the file (e.g., 100). If omitted, reads the entire file."
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# Todo list tool definitions
TODO_LIST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a new task to the todo list. Returns the task ID. Use this to break down complex workflows into manageable steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "A clear description of the task to be completed"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional additional notes or context for the task"
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_task",
            "description": "Mark a task as currently being worked on (in_progress status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to start"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed. Optionally add completion notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to complete"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the completion (e.g., results, findings)"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all tasks in the todo list. Can filter by status: 'all' (default), 'pending', 'in_progress', 'completed', or 'failed'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'all', 'pending', 'in_progress', 'completed', 'failed'. Default is 'all'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_next_task",
            "description": "Get the next pending task that should be worked on. Returns the task ID and description, or a message if all tasks are completed.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_progress",
            "description": "Get overall progress summary showing completion statistics.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fail_task",
            "description": "Mark a task as failed with an optional reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to mark as failed"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for the failure"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_details",
            "description": "Get detailed information about a specific task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to get details for"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clear_completed_tasks",
            "description": "Remove all completed tasks from the todo list.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# Parent agent tools (includes run_subagent, read_skill, and todo_list)
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "Read the full content of a skill by name. Use this when you need detailed information about a specific skill's usage, input/output, or reference materials. Available skills can be listed using list_skills.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to read (e.g., 'Motion Correction', 'CTF Estimation')"
                    }
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills with their names and descriptions. Use this to discover what domain knowledge is available before reading specific skills.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assess_dataset",
            "description": "Assess the quality of a cryo-ET dataset directory. Reads tilt angles (.tlt/.rawtlt), MRC stack statistics (.st/.mrc), alignment transformations (.xf), and CTF estimation output to generate a comprehensive quality report covering tilt coverage, image statistics, alignment drift, and CTF quality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_path": {
                        "type": "string",
                        "description": "Path to the dataset directory containing .st/.mrc, .tlt/.rawtlt, .xf, and optional CTF output files."
                    }
                },
                "required": ["dataset_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_mrc",
            "description": "Inspect a single MRC/ST file and return detailed header information plus per-slice statistics. Use this to examine individual tomograms or tilt series stacks in detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .mrc or .st file to inspect."
                    },
                    "num_slices": {
                        "type": "integer",
                        "description": "Number of evenly-spaced slices to sample for statistics. Default is 5."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
] + TODO_LIST_TOOLS
