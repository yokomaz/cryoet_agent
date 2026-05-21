"""
Command line interface for cryoet_agent.
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from prompt_toolkit import prompt

from cryoet_agent.prompts import SYSTEM_PROMPT
from cryoet_agent.tools import TOOLS, TOOL_HANDLERS
from cryoet_agent.tools.todo_list import get_todo_list

load_dotenv(override=True)

# Setup
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")

# Todo list related tools that should trigger a status print
TODO_LIST_TOOLS = {'add_task', 'start_task', 'complete_task', 'fail_task', 'list_tasks'}


def print_todo_status():
    """Print current todo list status."""
    todo = get_todo_list()
    if not todo.tasks:
        return
    
    print("\n📋 Current Todo List:")
    print("-" * 50)
    for task in todo.tasks:
        status_icon = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(task.status, "❓")
        print(f"  {status_icon} [{task.id}] {task.description} ({task.status})")
    
    summary = todo.get_summary()
    print(f"\n  📊 Progress: {summary['completed']}/{summary['total']} ({summary['progress_percentage']}%)")
    print("-" * 50)


def agent_loop(messages: list, client):
    """Agent loop with tool execution support."""
    while True:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            max_tokens=1024,
            tools=TOOLS,
        )
        
        message = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": message.tool_calls,
            **({"reasoning_content": message.reasoning_content} if hasattr(message, 'reasoning_content') and message.reasoning_content else {})
        })
        
        if not message.tool_calls:
            if message.content:
                print(f"Agent Final: {message.content}")
            return
        
        results = []
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            print(f"> agent > {tool_name}({tool_args})")

            handler = TOOL_HANDLERS.get(tool_name)
            try:
                if handler:
                    output = handler(**tool_args)
                else:
                    output = f"Unknown tool: {tool_name}"
            except Exception as e:
                output = f"Error: {e}"
            
            # Print todo list status after todo-related operations
            if tool_name in TODO_LIST_TOOLS:
                print_todo_status()
            
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })
        
        messages.extend(results)


def main():
    """Main entry point for cryoet_agent CLI."""
    if not API_KEY or not MODEL_ID:
        print("Error: Missing API_KEY or MODEL_ID in environment variables.")
        print("Please check your .env file.")
        return
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, max_retries=3)
    
    print("🧬 CryoEM Agent initialized.")
    print("Type 'q', 'exit', or press Enter to quit.\n")
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    while True:
        # query = input("\033[36mcryoet_agent >> \033[0m")
        query = prompt("cryoet_agent >> ")
        if query.strip().lower() in ("q", "exit", ""):
            print("Bye!")
            break
        
        messages.append({"role": "user", "content": query})
        agent_loop(messages, client)


if __name__ == "__main__":
    main()
