#!/usr/bin/env python3
# Usage: uv run ./aigent.py "hi"
# /// script
# dependencies = ["requests>=2.31.0"]
# ///

import json, sys, subprocess, os
import requests

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.0.100:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "none")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen")
MAX_TURNS = 1000

SYSTEM_PROMPT = """\
You are a coding agent. Your job is to help the user with programming tasks.

You have access to ONE tool: `bash` — which executes shell commands and returns stdout/stderr.

Workflow:
1. Plan what needs to be done.
2. Use `bash` to read files, run commands, write code, etc.
3. After gathering enough information or completing the task, give your final answer in natural language.
4. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""

LLM_TOOLS = [
    {"type": "function",
     "function": {"name": "bash",
                  "description": "Execute a shell command and return the output.",
                  "parameters": {"type": "object",
                                 "properties": {
                                     "command": {"type": "string", "description": "The bash command to execute."}
                                 },
                                 "required": ["command"]}
                 }
            }]

def run_bash(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = result.stdout + (f"\nSTDERR:\n{result.stderr}" if result.stderr else "")
        return f"Exit code: {result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"

def call_tool(name: str, arguments: dict) -> str:
    func = {"bash": run_bash}.get(name)
    if not func:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**arguments)
    except Exception as e:
        return f"Error calling {name}: {e}"

LLM_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}

def call_llm(messages):
    payload = {"model": LLM_MODEL, "messages": messages, "tools": LLM_TOOLS, "tool_choice": "auto",
               "temperature": 0.1, "max_tokens": 4096}
    resp = requests.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=LLM_HEADERS)
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    tool_calls = msg.get("tool_calls") or []
    return content, tool_calls

def agent_loop(user_message: str) -> None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    for turn in range(1, MAX_TURNS + 1):
        print(f"\n{'='*60}\n🔄 Turn {turn}\n{'='*60}")
        content, tool_calls = call_llm(messages)
        if content:
            print(f"\n🤖 {content}")
        if not tool_calls:
            print("(no text output)" if not content else "")
            print("✅ Agent finished")
            return
        prefix = "\n" if content else ""
        for tc in tool_calls:
            fn = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            tid = tc["id"]
            print(f"{prefix}🔧 Tool: {fn}({json.dumps(args, ensure_ascii=False)})")
            result = call_tool(fn, args)
            print(f"   → {result[:500]}{'...' if len(result)>500 else ''}")
            messages.append({"role": "assistant", "content": content or None, "tool_calls": [tc]})
            messages.append({"role": "tool", "tool_call_id": tid, "content": result})
    print(f"\n⚠️  Max turns ({MAX_TURNS}) reached. Stopping.")

if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not prompt.strip():
        print("No task provided. Exiting.")
        sys.exit(1)
    agent_loop(prompt)
