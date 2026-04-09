"""
LLM Function Calling Adapter for Shell Tool

This module provides integration between LLM function calling (e.g., Anthropic Claude, OpenAI)
and the shell execution tool. It handles the JSON schema format required by LLMs.

Usage with Anthropic Claude:
    from tools.shell_llm_adapter import SHELL_TOOL_SCHEMA, execute_shell_tool
    
    # Define tools for Claude
    tools = [SHELL_TOOL_SCHEMA]
    
    # When Claude responds with a tool call
    result = execute_shell_tool(tool_call_arguments)
"""

from __future__ import annotations

import json
from typing import Any

from tools.shell import run_shell, ShellResult


# JSON Schema for LLM function calling
SHELL_TOOL_SCHEMA = {
    "name": "shell",
    "description": "Execute a shell command. Use this tool to explore the filesystem, edit files, run scripts, get system information, etc.\n\n**Output:**\nThe stdout and stderr will be combined and returned as a string. The output may be truncated if it is too long. If the command failed, the exit code will be provided in a system tag.\n\n**Guidelines for safety and security:**\n- Each shell tool call will be executed in a fresh shell environment. The shell variables, current working directory changes, and the shell history is not preserved between calls.\n- The tool call will return after the command is finished. You shall not use this tool to execute an interactive command or a command that may run forever. For possibly long-running commands, you shall set timeout argument to a reasonable value.\n- Avoid using .. to access files or directories outside of the working directory.\n- Avoid modifying files outside of the working directory unless explicitly instructed to do so.\n- Never run commands that require superuser privileges unless explicitly instructed to do so.\n\n**Guidelines for efficiency:**\n- For multiple related commands, use && to chain them in a single call, e.g. cd /path && ls -la\n- Use ; to run commands sequentially regardless of success/failure\n- Use || for conditional execution (run second command only if first fails)\n- Use pipe operations (|) and redirections (>, >>) to chain input and output between commands\n- Always quote file paths containing spaces with double quotes (e.g., cd '/path with spaces/')\n- Use if, case, for, while control flows to execute complex logic in a single call.\n- Verify directory structure before create/edit/delete files or directories to reduce the risk of failure.\n\n**Commands available:**\n- Shell environment: cd, pwd, export, unset, env\n- File system operations: ls, find, mkdir, rm, cp, mv, touch, chmod, chown\n- File viewing/editing: cat, grep, head, tail, diff, patch\n- Text processing: awk, sed, sort, uniq, wc\n- System information/operations: ps, kill, top, df, free, uname, whoami, id, date\n- Network operations: curl, wget, ping, telnet, ssh\n- Archive operations: tar, zip, unzip\n- Other: Other commands available in the shell environment. Check the existence of a command by running which <command> before using it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute."
            },
            "timeout": {
                "type": "integer",
                "description": "The timeout in seconds for the command to execute. If the command takes longer than this, it will be killed.",
                "default": 60,
                "minimum": 1,
                "maximum": 300
            }
        },
        "required": ["command"]
    }
}


def execute_shell_tool(arguments: dict[str, Any], work_dir: str | None = None) -> dict[str, Any]:
    """
    Execute the shell tool with arguments from LLM function call.
    
    Args:
        arguments: The arguments dict from LLM tool call (contains 'command' and optionally 'timeout')
        work_dir: Optional working directory to execute command in
        
    Returns:
        Dictionary with the tool execution result for LLM consumption
        
    Example:
        >>> result = execute_shell_tool({"command": "ls -la", "timeout": 30})
        >>> print(result)
        {
            "output": "file1.txt\nfile2.txt",
            "exit_code": 0,
            "success": True
        }
    """
    command = arguments.get("command", "").strip()
    
    if not command:
        return {
            "output": "Error: Command cannot be empty.",
            "exit_code": -1,
            "success": False
        }
    
    timeout = arguments.get("timeout", 60)
    
    try:
        result = run_shell(command, work_dir=work_dir, timeout=timeout)
        
        # Format output for LLM
        output = result.output
        if result.exit_code != 0:
            output = f"{output}\n\n[Exit code: {result.exit_code}]"
        
        return {
            "output": output,
            "exit_code": result.exit_code,
            "success": result.exit_code == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    except TimeoutError as e:
        return {
            "output": f"Error: {str(e)}",
            "exit_code": -1,
            "success": False
        }
    except ValueError as e:
        # Dangerous command or validation error
        return {
            "output": f"Error: {str(e)}",
            "exit_code": -1,
            "success": False
        }
    except Exception as e:
        return {
            "output": f"Error executing command: {str(e)}",
            "exit_code": -1,
            "success": False
        }


# Anthropic Claude specific adapter
def get_anthropic_tools() -> list[dict[str, Any]]:
    """
    Get tools formatted for Anthropic Claude API.
    
    Returns:
        List of tool definitions for Claude's tools parameter
    """
    return [SHELL_TOOL_SCHEMA]


def handle_anthropic_tool_call(tool_name: str, tool_input: dict[str, Any], work_dir: str | None = None) -> dict[str, Any]:
    """
    Handle a tool call from Anthropic Claude.
    
    Args:
        tool_name: The name of the tool being called
        tool_input: The input arguments from Claude
        work_dir: Optional working directory
        
    Returns:
        Tool result formatted for Claude
    """
    if tool_name == "shell":
        return execute_shell_tool(tool_input, work_dir=work_dir)
    else:
        return {
            "output": f"Unknown tool: {tool_name}",
            "exit_code": -1,
            "success": False
        }


# OpenAI specific adapter
def get_openai_tools() -> list[dict[str, Any]]:
    """
    Get tools formatted for OpenAI API (GPT-4, etc.).
    
    Returns:
        List of tool definitions for OpenAI's tools parameter
    """
    # OpenAI uses slightly different schema format
    return [{
        "type": "function",
        "function": {
            "name": SHELL_TOOL_SCHEMA["name"],
            "description": SHELL_TOOL_SCHEMA["description"],
            "parameters": SHELL_TOOL_SCHEMA["input_schema"]
        }
    }]


def handle_openai_tool_call(function_name: str, function_args: str | dict[str, Any], work_dir: str | None = None) -> str:
    """
    Handle a tool call from OpenAI.
    
    Args:
        function_name: The name of the function being called
        function_args: The arguments (JSON string or dict)
        work_dir: Optional working directory
        
    Returns:
        Tool result as string for OpenAI
    """
    if isinstance(function_args, str):
        args = json.loads(function_args)
    else:
        args = function_args
    
    if function_name == "shell":
        result = execute_shell_tool(args, work_dir=work_dir)
        return result["output"]
    else:
        return f"Unknown function: {function_name}"


# Generic adapter for any LLM
def get_llm_tools(provider: str = "anthropic") -> list[dict[str, Any]]:
    """
    Get tools formatted for specific LLM provider.
    
    Args:
        provider: One of "anthropic", "openai", or "generic"
        
    Returns:
        List of tool definitions
    """
    if provider.lower() == "anthropic":
        return get_anthropic_tools()
    elif provider.lower() == "openai":
        return get_openai_tools()
    else:
        # Generic format (same as Anthropic)
        return [SHELL_TOOL_SCHEMA]


def handle_tool_call(
    tool_name: str,
    tool_input: dict[str, Any] | str,
    work_dir: str | None = None,
    provider: str = "anthropic"
) -> dict[str, Any] | str:
    """
    Generic handler for tool calls from any LLM provider.
    
    Args:
        tool_name: Name of the tool/function
        tool_input: Tool arguments
        work_dir: Optional working directory
        provider: LLM provider name
        
    Returns:
        Tool result (format depends on provider)
    """
    if tool_name == "shell":
        if isinstance(tool_input, str):
            tool_input = json.loads(tool_input)
        
        result = execute_shell_tool(tool_input, work_dir=work_dir)
        
        if provider.lower() == "openai":
            return result["output"]
        else:
            return result
    else:
        error_msg = f"Unknown tool: {tool_name}"
        if provider.lower() == "openai":
            return error_msg
        else:
            return {"output": error_msg, "exit_code": -1, "success": False}


if __name__ == "__main__":
    # Test the adapter
    print("Testing shell tool adapter...")
    print()
    
    # Print the schema
    print("Tool Schema:")
    print(json.dumps(SHELL_TOOL_SCHEMA, indent=2))
    print()
    
    # Test execution
    print("Test 1: Basic command")
    result = execute_shell_tool({"command": "echo 'Hello World'"})
    print(f"Result: {result}")
    print()
    
    print("Test 2: Command with timeout")
    result = execute_shell_tool({"command": "sleep 1 && echo done", "timeout": 5})
    print(f"Result: {result}")
    print()
    
    print("Test 3: Failing command")
    result = execute_shell_tool({"command": "false"})
    print(f"Result: {result}")
    print()
    
    print("Test 4: Dangerous command")
    result = execute_shell_tool({"command": "sudo apt-get install something"})
    print(f"Result: {result}")
    print()
    
    print("All tests completed!")
