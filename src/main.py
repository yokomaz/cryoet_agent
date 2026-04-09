import os
import json
from dotenv import load_dotenv
import uuid
import time


from openai import OpenAI

from prompts import PROMPT
from tools import TOOLS, TOOL_HANDLERS

load_dotenv(override=True)

# Setup
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
SYSTEM_PROMPT = PROMPT.SYSTEM_PROMPT


def agent_loop(messages: list):
    """Agent loop with tool execution support."""
    while True:
        # LLM call
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            max_tokens=1024,
            tools=TOOLS,
        )
        
        message = response.choices[0].message
        print(message)
        # messages.append({"role": "assistant", "content": message.content or "", "tool_calls": message.tool_calls if message.tool_calls else []})
        messages.append({"role": "assistant", "content": message.content or "", "tool_calls": message.tool_calls, **({"reasoning_content": message.reasoning_content} if hasattr(message, 'reasoning_content') and message.reasoning_content else {})})
        # Check if the model wants to use tools
        if not message.tool_calls:
            # No tool calls, just print the response
            if message.content:
                print(message.content)
            return
        
        # Tool execution
        results = []
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}
            
            # Execute tool
            handler = TOOL_HANDLERS.get(tool_name)
            try:
                if handler:
                    output = handler(**tool_args)
                else:
                    output = f"Unknown tool: {tool_name}"
            except Exception as e:
                output = f"Error: {e}"
            
            print(f"> {tool_name}({tool_args}): {str(output)[:2000]}")
            
            # Add tool result to results
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })
        
        # Append all tool results to messages
        messages.extend(results)
        print(messages)

def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        query = input("\033[36mcryoet_agent >> \033[0m")

        if query.strip().lower() in ("q", "exit", ""):
            print("Bye!")
            break
        
        messages.append({"role": "user", "content": query})
        agent_loop(messages)


if __name__ == "__main__":
    main()
