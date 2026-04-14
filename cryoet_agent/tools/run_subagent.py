"""
Subagent tool for cryoet_agent.

Spawns a child agent with isolated context to extract structured workflow from PDF files.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI

from cryoet_agent.prompts import SUBAGENT_PROMPT
from cryoet_agent.tools.pdf_parser import pdf_parser_safe
from cryoet_agent.tools.shell import run_shell

# Load environment for subagent
load_dotenv(override=True)

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")


# Tool definitions for subagent
# These are defined here to avoid circular imports
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

SUBAGENT_TOOLS = BASE_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "pdf_parser",
            "description": "Extract text content from a PDF file. Useful for parsing academic papers and method sections to extract data processing workflows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the PDF file to parse"
                    }
                },
                "required": ["pdf_path"]
            }
        }
    }
]


# Tool handlers available to subagent
SUBAGENT_HANDLERS = {
    "run_shell": lambda **kw: str(run_shell(kw["command"])),
    "pdf_parser": lambda **kw: pdf_parser_safe(kw["pdf_path"]),
}


@dataclass
class SubagentResult:
    """Result of subagent execution."""
    
    text: str
    iterations: int
    success: bool
    error: str | None = None
    
    def __str__(self):
        return self.text


def run_subagent(prompt: str, max_iterations: int = 10) -> str:
    """
    Run a subagent with isolated context to parse PDF and extract workflow.
    
    Args:
        prompt: The prompt containing the PDF path and instructions for the subagent.
        max_iterations: Maximum number of tool use iterations
        
    Returns:
        Extracted workflow as JSON string
    """
    if not API_KEY or not MODEL_ID:
        raise ValueError("Missing API configuration")
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    # Fresh context for subagent
    messages = [
        {"role": "system", "content": SUBAGENT_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    try:
        for iteration in range(max_iterations):
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                tools=SUBAGENT_TOOLS,
                max_tokens=1024,
            )
            
            message = response.choices[0].message
            
            # Add assistant response to messages
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            })
            
            # Check if done (no tool calls)
            if not message.tool_calls:
                content = message.content or "{}"
                result = SubagentResult(
                    text=content,
                    iterations=iteration + 1,
                    success=True,
                )
                print(str(result))
                exit()
                return str(result)
            
            # Execute tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                # Execute tool handler
                handler = SUBAGENT_HANDLERS.get(tool_name)
                if handler:
                    try:
                        output = handler(**tool_args)
                    except Exception as e:
                        output = f"Error: {e}"
                else:
                    output = f"Unknown tool: {tool_name}"
                
                print(f"> subagent > {tool_name}({tool_args})")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(output)[:50000],
                })
        
        # Max iterations reached
        result = SubagentResult(
            text="{}",
            iterations=max_iterations,
            success=False,
            error="Max iterations exceeded",
        )
        print(f"======={str(result)}=========")
        exit()
        return str(result)
        
    except Exception as e:
        result = SubagentResult(
            text="{}",
            iterations=0,
            success=False,
            error=str(e),
        )
    print(f"--------{str(result)}-------")
    exit()
    return str(result)
