"""
Todo List tool for cryoet_agent.

Provides task management functionality for the agent to track workflow progress.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Task:
    """Represents a single task in the todo list."""
    id: int
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


class TodoList:
    """Manages a list of tasks for workflow tracking."""
    
    def __init__(self):
        self.tasks: list[Task] = []
        self._next_id = 1
    
    def add_task(self, description: str, notes: str = "") -> Task:
        """Add a new task to the list."""
        task = Task(
            id=self._next_id,
            description=description,
            notes=notes
        )
        self.tasks.append(task)
        self._next_id += 1
        return task
    
    def start_task(self, task_id: int) -> Optional[Task]:
        """Mark a task as in_progress."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "in_progress"
                return task
        return None
    
    def complete_task(self, task_id: int, notes: str = "") -> Optional[Task]:
        """Mark a task as completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "completed"
                task.completed_at = datetime.now().isoformat()
                if notes:
                    task.notes = notes
                return task
        return None
    
    def fail_task(self, task_id: int, reason: str = "") -> Optional[Task]:
        """Mark a task as failed."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "failed"
                if reason:
                    task.notes = reason
                return task
        return None
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a specific task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def list_tasks(self, status: Optional[str] = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self.tasks if t.status == status]
        return self.tasks.copy()
    
    def get_next_pending_task(self) -> Optional[Task]:
        """Get the next pending task (lowest ID)."""
        pending = [t for t in self.tasks if t.status == "pending"]
        if pending:
            return min(pending, key=lambda t: t.id)
        return None
    
    def get_summary(self) -> dict:
        """Get a summary of all tasks."""
        total = len(self.tasks)
        completed = len([t for t in self.tasks if t.status == "completed"])
        pending = len([t for t in self.tasks if t.status == "pending"])
        in_progress = len([t for t in self.tasks if t.status == "in_progress"])
        failed = len([t for t in self.tasks if t.status == "failed"])
        
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "failed": failed,
            "progress_percentage": round(completed / total * 100, 1) if total > 0 else 0
        }
    
    def clear_completed(self) -> int:
        """Remove all completed tasks. Returns count removed."""
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.status != "completed"]
        return original_count - len(self.tasks)
    
    def to_json(self) -> str:
        """Export all tasks as JSON."""
        return json.dumps({
            "tasks": [t.to_dict() for t in self.tasks],
            "summary": self.get_summary()
        }, indent=2)
    
    def format_list(self) -> str:
        """Format tasks as a readable list."""
        if not self.tasks:
            return "No tasks in the list."
        
        lines = ["📋 Todo List:", ""]
        
        for task in self.tasks:
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(task.status, "❓")
            
            lines.append(f"{status_icon} [{task.id}] {task.description}")
            if task.notes:
                lines.append(f"    📝 {task.notes}")
        
        summary = self.get_summary()
        lines.extend([
            "",
            f"📊 Progress: {summary['completed']}/{summary['total']} ({summary['progress_percentage']}%)"
        ])
        
        return "\n".join(lines)


# Global todo list instance (per session)
_todo_list: Optional[TodoList] = None


def get_todo_list() -> TodoList:
    """Get or create the global todo list instance."""
    global _todo_list
    if _todo_list is None:
        _todo_list = TodoList()
    return _todo_list


def reset_todo_list() -> None:
    """Reset the todo list (for testing)."""
    global _todo_list
    _todo_list = TodoList()


# Tool functions for agent

def add_task(description: str, notes: str = "") -> str:
    """Add a new task to the todo list."""
    todo = get_todo_list()
    task = todo.add_task(description, notes)
    return f"Added task [{task.id}]: {description}"


def start_task(task_id: int) -> str:
    """Mark a task as in progress."""
    todo = get_todo_list()
    task = todo.start_task(task_id)
    if task:
        return f"Started task [{task.id}]: {task.description}"
    return f"Task {task_id} not found"


def complete_task(task_id: int, notes: str = "") -> str:
    """Mark a task as completed."""
    todo = get_todo_list()
    task = todo.complete_task(task_id, notes)
    if task:
        result = f"Completed task [{task.id}]: {task.description}"
        if notes:
            result += f"\nNotes: {notes}"
        return result
    return f"Task {task_id} not found"


def fail_task(task_id: int, reason: str = "") -> str:
    """Mark a task as failed."""
    todo = get_todo_list()
    task = todo.fail_task(task_id, reason)
    if task:
        return f"Failed task [{task.id}]: {task.description}\nReason: {reason}"
    return f"Task {task_id} not found"


def list_tasks(status: str = "all") -> str:
    """List all tasks. Use status='pending'/'completed'/'in_progress'/'failed' to filter."""
    todo = get_todo_list()
    
    if status == "all":
        return todo.format_list()
    
    tasks = todo.list_tasks(status)
    if not tasks:
        return f"No {status} tasks found."
    
    lines = [f"Tasks with status '{status}':", ""]
    for task in tasks:
        lines.append(f"[{task.id}] {task.description}")
    return "\n".join(lines)


def get_next_task() -> str:
    """Get the next pending task that should be worked on."""
    todo = get_todo_list()
    task = todo.get_next_pending_task()
    
    if task:
        return f"Next task: [{task.id}] {task.description}"
    
    # Check if all completed
    summary = todo.get_summary()
    if summary["total"] > 0 and summary["pending"] == 0:
        return "🎉 All tasks completed! No more pending tasks."
    
    return "No pending tasks. Use add_task to create new tasks."


def get_task_details(task_id: int) -> str:
    """Get detailed information about a specific task."""
    todo = get_todo_list()
    task = todo.get_task(task_id)
    
    if not task:
        return f"Task {task_id} not found"
    
    status_icon = {
        "pending": "⏳",
        "in_progress": "🔄",
        "completed": "✅",
        "failed": "❌"
    }.get(task.status, "❓")
    
    lines = [
        f"Task [{task.id}] Details:",
        f"  Description: {task.description}",
        f"  Status: {status_icon} {task.status}",
        f"  Created: {task.created_at}"
    ]
    
    if task.completed_at:
        lines.append(f"  Completed: {task.completed_at}")
    
    if task.notes:
        lines.append(f"  Notes: {task.notes}")
    
    return "\n".join(lines)


def get_progress() -> str:
    """Get overall progress summary."""
    todo = get_todo_list()
    summary = todo.get_summary()
    
    return (
        f"📊 Overall Progress: {summary['completed']}/{summary['total']} tasks "
        f"({summary['progress_percentage']}%)\n"
        f"  ✅ Completed: {summary['completed']}\n"
        f"  ⏳ Pending: {summary['pending']}\n"
        f"  🔄 In Progress: {summary['in_progress']}\n"
        f"  ❌ Failed: {summary['failed']}"
    )


def clear_completed_tasks() -> str:
    """Remove all completed tasks from the list."""
    todo = get_todo_list()
    count = todo.clear_completed()
    return f"Cleared {count} completed tasks."
