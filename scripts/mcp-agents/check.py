#!/usr/bin/env python3
"""Smoke-test every server in mcp.json: initialize + tools/list over stdio.
Usage: ./check.py [mcp.json]   (exit 0 when all servers respond)
"""
import json, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor

MESSAGES = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "check", "version": "1"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
]
TIMEOUT = 60

def probe(name, cfg):
    cmd = [cfg["command"], *cfg.get("args", [])]
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        return name, f"FAIL  {cmd[0]} not installed"

    lines = []
    def read():
        for line in p.stdout:
            lines.append(line)
            try:
                if json.loads(line).get("id") == 2:
                    break
            except ValueError:
                pass
    t = threading.Thread(target=read, daemon=True)
    t.start()
    try:
        for m in MESSAGES:
            p.stdin.write(json.dumps(m) + "\n")
        p.stdin.flush()
    except BrokenPipeError:
        pass
    t.join(TIMEOUT)
    p.kill()

    version, tools = "", 0
    for line in lines:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("id") == 1:
            version = msg.get("result", {}).get("serverInfo", {}).get("version", "")
        elif msg.get("id") == 2:
            tools = len(msg.get("result", {}).get("tools", []))
    if tools:
        return name, f"OK   {tools:>3} tools  {version}"
    err = (p.stderr.read().strip().splitlines() or ["no response"])[-1]
    return name, f"FAIL  {err[:120]}"

servers = list(json.load(open(sys.argv[1] if len(sys.argv) > 1 else "mcp.json"))["servers"].items())
results = list(map(lambda kv: probe(*kv), servers))
for name, status in sorted(results):
    print(f"{name:18} {status}")
failed = [n for n, s in results if s.startswith("FAIL")]
print(f"\n{len(results) - len(failed)}/{len(results)} OK" + (f" — {', '.join(failed)}" if failed else ""))
sys.exit(1 if failed else 0)
