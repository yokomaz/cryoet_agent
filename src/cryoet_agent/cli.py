from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from cryoet_agent.app import CryoETAgentApp


DATASET_HINT_RE = re.compile(r"(?:dataset|data)\s+at\s+([^\s,]+)", re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryoet-agent")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Generate a workflow plan.")
    plan_parser.add_argument("--data", default=".", help="Dataset path relative to the current workspace.")
    plan_parser.add_argument("--message", required=True, help="Natural-language planning request.")
    plan_parser.add_argument("--model-provider", default=None, help="Model provider override, for example 'ollama'.")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect the workspace dataset.")
    inspect_parser.add_argument("--data", default=".", help="Dataset path relative to the current workspace.")
    inspect_parser.add_argument("--model-provider", default=None, help="Model provider override, for example 'ollama'.")

    chat_parser = subparsers.add_parser("chat", help="Start the interactive planner shell.")
    chat_parser.add_argument("--model-provider", default=None, help="Model provider override, for example 'ollama'.")
    return parser


def infer_dataset_path(message: str) -> str:
    match = DATASET_HINT_RE.search(message)
    if match:
        return match.group(1).strip().strip("\"'")
    return "."


def run_chat(model_provider: str | None = None) -> int:
    app = CryoETAgentApp(model_provider=model_provider)
    print("CryoET planning agent")
    print("Workspace scope:", Path.cwd())
    print("Type a natural-language request, or 'exit' to quit.")
    while True:
        try:
            message = input("cryoet-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message or message.lower() in {"exit", "quit"}:
            return 0
        dataset_path = infer_dataset_path(message)
        summary, _, _ = app.plan_request(user_message=message, dataset_path=dataset_path)
        print(summary)
        print()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        return run_chat()

    app = CryoETAgentApp(model_provider=getattr(args, "model_provider", None))
    if args.command == "plan":
        summary, _, _ = app.plan_request(args.message, dataset_path=args.data)
        print(summary)
        return 0
    if args.command == "inspect":
        print(app.inspect(args.data))
        return 0
    if args.command == "chat":
        return run_chat(args.model_provider)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
