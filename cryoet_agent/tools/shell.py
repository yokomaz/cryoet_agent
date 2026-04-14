"""
Shell command execution tool for cryoet_agent.

Based on Kimi CLI's Shell tool implementation.
Provides a safe and flexible way to execute shell commands.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class ShellResult:
    """Result of a shell command execution."""
    
    stdout: str
    stderr: str
    exit_code: int
    command: str
    
    @property
    def output(self) -> str:
        """Combined stdout and stderr output."""
        return (self.stdout + self.stderr).strip()
    
    def __str__(self) -> str:
        return self.output


# Dangerous command patterns to block
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf $HOME",
    "> /dev/sda",
    "dd if=",
    "mkfs.",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
]


def is_dangerous_command(command: str) -> tuple[bool, str | None]:
    """
    Check if a command contains dangerous patterns.
    
    Args:
        command: The command to check
        
    Returns:
        Tuple of (is_dangerous, reason)
    """
    cmd_lower = command.lower().strip()
    
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in cmd_lower:
            return True, f"Dangerous pattern detected: {pattern}"
    
    # Check for sudo (unless it's just checking sudo version or help)
    if cmd_lower.startswith("sudo ") or " sudo " in cmd_lower:
        if not ("--version" in cmd_lower or "--help" in cmd_lower or "-h" in cmd_lower):
            return True, "Commands with sudo require explicit user approval"
    
    return False, None


def validate_path_in_workdir(command: str, work_dir: Path) -> tuple[bool, str | None]:
    """
    Check if the command tries to access paths outside the working directory.
    
    Args:
        command: The command to check
        work_dir: The allowed working directory
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Simple check for ../ patterns
    if ".." in command:
        return False, "Avoid using '..' to access files or directories outside of the working directory"

    return True, None


def run_shell(
    command: str,
    work_dir: str | Path | None = None,
    timeout: int = 60,
    max_output_length: int = 50000,
    check_dangerous: bool = True,
    env: dict[str, str] | None = None,
) -> ShellResult:
    """
    Execute a shell command safely.
    
    This is the synchronous version. Each call runs in a fresh shell environment.
    Shell variables, current working directory changes, and shell history are not 
    preserved between calls.
    
    Args:
        command: The shell command to execute
        work_dir: Working directory for command execution. If None, uses current directory.
        timeout: Maximum execution time in seconds (default: 60, max: 300)
        max_output_length: Maximum length of output to return (default: 50000)
        check_dangerous: Whether to check for dangerous command patterns (default: True)
        env: Additional environment variables to set
        
    Returns:
        ShellResult object containing stdout, stderr, and exit code
        
    Raises:
        ValueError: If command is empty or dangerous patterns detected
        TimeoutError: If command exceeds timeout
        
    Examples:
        >>> result = run_shell("ls -la")
        >>> print(result.output)
        
        >>> result = run_shell("cd /tmp && pwd", work_dir="/home/user")
        >>> print(result.exit_code)  # 0 if success
    """
    # Validate command
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")
    
    command = command.strip()
    
    # Check for dangerous commands
    if check_dangerous:
        is_danger, reason = is_dangerous_command(command)
        if is_danger:
            raise ValueError(f"Command blocked: {reason}")
    
    # Resolve working directory
    if work_dir is None:
        work_dir = Path.cwd()
    else:
        work_dir = Path(work_dir).resolve()
    
    # Validate working directory
    if not work_dir.exists():
        raise ValueError(f"Working directory does not exist: {work_dir}")
    
    # Check for path escape attempts
    if check_dangerous:
        is_valid, error = validate_path_in_workdir(command, work_dir)
        if not is_valid:
            raise ValueError(error)
    
    # Clamp timeout
    timeout = max(1, min(timeout, 300))  # Between 1 and 300 seconds
    
    # Prepare environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        # Truncate output if too long
        if len(stdout) > max_output_length:
            stdout = stdout[:max_output_length] + f"\n... ({len(result.stdout) - max_output_length} more chars)"
        if len(stderr) > max_output_length:
            stderr = stderr[:max_output_length] + f"\n... ({len(result.stderr) - max_output_length} more chars)"
        
        return ShellResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            command=command,
        )
        
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command killed by timeout ({timeout}s)")
    except Exception as e:
        raise RuntimeError(f"Failed to execute command: {e}")

async def run_shell_async(
    command: str,
    work_dir: str | Path | None = None,
    timeout: int = 60,
    max_output_length: int = 50000,
    check_dangerous: bool = True,
    env: dict[str, str] | None = None,
    stdout_callback: Callable[[str], None] | None = None,
    stderr_callback: Callable[[str], None] | None = None,
) -> ShellResult:
    """
    Execute a shell command asynchronously.
    
    This is the async version that allows streaming output via callbacks.
    
    Args:
        command: The shell command to execute
        work_dir: Working directory for command execution
        timeout: Maximum execution time in seconds
        max_output_length: Maximum length of output to return
        check_dangerous: Whether to check for dangerous command patterns
        env: Additional environment variables to set
        stdout_callback: Optional callback for stdout lines
        stderr_callback: Optional callback for stderr lines
        
    Returns:
        ShellResult object containing stdout, stderr, and exit code
    """
    # Validate command
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")
    
    command = command.strip()
    
    # Check for dangerous commands
    if check_dangerous:
        is_danger, reason = is_dangerous_command(command)
        if is_danger:
            raise ValueError(f"Command blocked: {reason}")
    
    # Resolve working directory
    if work_dir is None:
        work_dir = Path.cwd()
    else:
        work_dir = Path(work_dir).resolve()
    
    if not work_dir.exists():
        raise ValueError(f"Working directory does not exist: {work_dir}")
    
    # Clamp timeout
    timeout = max(1, min(timeout, 300))
    
    # Prepare environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    
    # Detect shell
    shell_path = "/bin/bash"
    if not Path(shell_path).exists():
        shell_path = "/bin/sh"
    
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
            env=run_env,
            executable=shell_path,
        )
        
        async def read_stream(stream, callback, lines_list):
            while True:
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace")
                lines_list.append(line_str)
                if callback:
                    callback(line_str)
        
        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, stdout_callback, stdout_lines),
                read_stream(process.stderr, stderr_callback, stderr_lines),
            ),
            timeout,
        )
        
        exit_code = await process.wait()
        
        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)
        
        # Truncate if too long
        if len(stdout) > max_output_length:
            stdout = stdout[:max_output_length] + f"\n... (truncated)"
        if len(stderr) > max_output_length:
            stderr = stderr[:max_output_length] + f"\n... (truncated)"
        
        return ShellResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            command=command,
        )
        
    except asyncio.TimeoutError:
        try:
            process.kill()
            await process.wait()
        except:
            pass
        raise TimeoutError(f"Command killed by timeout ({timeout}s)")
    except Exception as e:
        raise RuntimeError(f"Failed to execute command: {e}")


# Convenience functions for common operations

def check_command_exists(command: str) -> bool:
    """Check if a command exists in the system PATH."""
    result = run_shell(f"which {command}", check_dangerous=False)
    return result.exit_code == 0 and result.output.strip()


def get_system_info() -> dict[str, str]:
    """Get basic system information."""
    info = {}
    
    # OS info
    result = run_shell("uname -a", check_dangerous=False)
    if result.exit_code == 0:
        info["os"] = result.output.strip()
    
    # Current directory
    result = run_shell("pwd", check_dangerous=False)
    if result.exit_code == 0:
        info["pwd"] = result.output.strip()
    
    # User
    result = run_shell("whoami", check_dangerous=False)
    if result.exit_code == 0:
        info["user"] = result.output.strip()
    
    return info