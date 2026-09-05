#!/usr/bin/env python3
# Usage: uv run ./aigent2.py "hi" [-v]
# /// script
# dependencies = ["requests>=2.31.0"]
# ///
"""LLM coding agent v2.

- stdout: короткая статус-строка на действие + финальный ответ (без -v).
- -v: полный вывод (текст модели, аргументы, preview результатов, heartbeat-строки).
- Всё действие асинхронно пишется в $AIGENT_DIR/<ts>-<id>.log (по умолчанию
  ~/.local/state/aigent), путь печатается в stdout на старте.
- Ошибки API: retry x3 (паузы 3/5/10s) на network/429/5xx, 4xx — сразу ошибка.
- Exit code: 0 = успех, 1 = ошибка/макс. turn'ов, 130 = Ctrl-C.
"""

import argparse
import base64
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from contextlib import contextmanager

import requests

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "none")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen")
LLM_HEADERS = {"Content-Type": "application/json",
               "Authorization": f"Bearer {LLM_API_KEY}"}

MAX_TURNS = 1000
BASH_TIMEOUT = 120
LLM_TIMEOUT = (10, 300)          # (connect, read)
RETRY_DELAYS = (3, 5, 10)        # 3 retry
MAX_TOOL_RESULT = 16_000         # обрезка tool-результата при отправке в LLM

AIGENT_DIR = os.getenv("AIGENT_DIR",
                       os.path.expanduser("~/.local/state/aigent"))
os.makedirs(AIGENT_DIR, exist_ok=True)

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
                                     "command": {"type": "string",
                                                 "description": "The bash command to execute."}
                                 },
                                 "required": ["command"]}
                 }
            }]

# --------------------------------------------------------------------------
# Logging: файл всегда (async writer-тред), stdout при -v
# --------------------------------------------------------------------------

VERBOSE = False
LOG_FILE = ""
_log_q: queue.Queue = queue.Queue()
_log_thread: threading.Thread | None = None


def start_log() -> None:
    global LOG_FILE, _log_thread
    LOG_FILE = os.path.join(
        AIGENT_DIR, f"{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}.log")
    open(LOG_FILE, "a").close()  # создать файл
    _log_thread = threading.Thread(target=_log_writer, daemon=True)
    _log_thread.start()
    print(f"📄 log: {LOG_FILE}", flush=True)


def stop_log() -> None:
    _log_q.put(None)  # sentinel: writer дописывает очередь и завершается
    if _log_thread:
        _log_thread.join(timeout=10)


def _log_writer() -> None:
    while True:
        line = _log_q.get()  # немедленный drain — tail -f видит без задержки
        if line is None:
            return
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def log(msg: str = "") -> None:
    """В файл всегда; в stdout только при -v."""
    _log_q.put(msg)
    if VERBOSE:
        print(msg, flush=True)


def status(msg: str) -> None:
    """Короткая строка прогресса: в stdout всегда + в файл."""
    print(msg, flush=True)
    _log_q.put(msg)


@contextmanager
def heartbeat(label: str, interval: int = 10):
    """Пока долгая операция (LLM/bash) идёт: строка в файл каждые N секунд,
    при -v — live-строка в stdout через \\r. Поток просыпается раз в секунду,
    чтобы не задерживать завершение операции."""
    stop = threading.Event()
    fired = [False]

    def tick():
        t0 = time.monotonic()
        last = 0
        while not stop.wait(1):
            el = int(time.monotonic() - t0)
            if el - last >= interval:
                last = el
                line = f"⏳ {label} — {el}s"
                _log_q.put(line)
                if VERBOSE:
                    fired[0] = True
                    print(f"\r{line}", end="", flush=True)

    th = threading.Thread(target=tick, daemon=True)
    th.start()
    try:
        yield
    finally:
        stop.set()
        th.join(timeout=5)
        if VERBOSE and fired[0]:
            print("\r" + " " * 72 + "\r", end="", flush=True)


# --------------------------------------------------------------------------
# LLM
# --------------------------------------------------------------------------

class LLMError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = False):
        super().__init__(msg)
        self.retryable = retryable


def call_llm(messages):
    """POST /chat/completions. Возвращает (content, tool_calls, finish_reason).

    Retry x3 (3/5/10s) на сетевые ошибки, 429, 5xx. 4xx — сразу LLMError.
    """
    payload = {"model": LLM_MODEL, "messages": messages, "tools": LLM_TOOLS,
               "tool_choice": "auto", "temperature": 0.1, "max_tokens": 4096}
    last_err = ""
    for attempt in range(1 + len(RETRY_DELAYS)):
        if attempt:
            log(f"⚠️ retry {attempt}/{len(RETRY_DELAYS)} in {RETRY_DELAYS[attempt - 1]}s")
            time.sleep(RETRY_DELAYS[attempt - 1])
        try:
            with heartbeat("LLM call"):
                resp = requests.post(f"{LLM_BASE_URL}/chat/completions",
                                     json=payload, headers=LLM_HEADERS,
                                     timeout=LLM_TIMEOUT)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}",
                               retryable=True)
            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]
            return ((msg.get("content") or "").strip(),
                    msg.get("tool_calls") or [],
                    choice.get("finish_reason"))
        except LLMError as e:
            last_err = str(e)
            if not e.retryable:
                raise
        except (requests.RequestException, ValueError, KeyError) as e:
            last_err = f"{type(e).__name__}: {e}"
    raise LLMError(f"LLM request failed after {1 + len(RETRY_DELAYS)} attempts: {last_err}")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

_CHILD: list = [None]  # активный дочерний процесс (чтобы SIGINT убил его)


def _on_int(signum, frame):
    child = _CHILD[0]
    if child:
        try:
            child.kill()
        except OSError:
            pass
    raise KeyboardInterrupt


def run_bash(command: str) -> str:
    label = "bash: " + " ".join(command.split())[:60]
    with heartbeat(label):
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        _CHILD[0] = p
        try:
            out, err = p.communicate(timeout=BASH_TIMEOUT)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            return f"Error: command timed out after {BASH_TIMEOUT}s"
        finally:
            _CHILD[0] = None
    out = out + (f"\nSTDERR:\n{err}" if err else "")
    return f"Exit code: {p.returncode}\n{out}"


def call_tool(name: str, arguments: dict) -> str:
    func = {"bash": run_bash}.get(name)
    if not func:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**arguments)
    except Exception as e:
        return f"Error calling {name}: {e}"


def _clip(s: str, limit: int = MAX_TOOL_RESULT) -> str:
    """Обрезка tool-результата перед отправкой в LLM (защита контекста)."""
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n[... truncated, {len(s) - limit} chars omitted]"


# --------------------------------------------------------------------------
# Images (перенесено из aigent.py)
# --------------------------------------------------------------------------

IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif"}
IMAGE_RE = re.compile(r"[\w./~-]+?\.(?:png|jpe?g|gif)", re.IGNORECASE)


def load_image(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except OSError as e:
        status(f"⚠️  failed to load image {path}: {e}")
        return None
    mime = IMAGE_MIME.get(os.path.splitext(path)[1].lower(), "image/png")
    return f"data:{mime};base64,{b64}"


def build_user_content(message: str) -> list | str:
    """Извлекает пути к картинкам из промпта; возвращает multimodal content, иначе str."""
    seen, paths = set(), []
    for raw in IMAGE_RE.findall(message):
        p = os.path.expanduser(raw)
        if os.path.exists(p) and p not in seen:
            seen.add(p)
            paths.append((raw, p))
    if not paths:
        return message
    text = message
    images = []
    for raw, p in paths:
        text = text.replace(raw, f"[image: {p}]", 1)
        url = load_image(p)
        if url:
            images.append({"type": "image_url", "image_url": {"url": url}})
    return [{"type": "text", "text": text.strip()}] + images


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------

def save_result(content: str, reason: str = "") -> str:
    path = os.path.join(
        AIGENT_DIR, f"{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content or f"({reason})")
    status(f"💾 saved: {path}")
    return path


# --------------------------------------------------------------------------
# Agent loop
# --------------------------------------------------------------------------

def agent_loop(user_message: str, system_prompt: str = SYSTEM_PROMPT) -> int:
    status(f"🔗 {LLM_BASE_URL} model={LLM_MODEL}" + (" [verbose]" if VERBOSE else ""))
    log(f"prompt: {user_message}")

    user_content = build_user_content(user_message)
    if isinstance(user_content, list):
        n = sum(1 for c in user_content if c.get("type") == "image_url")
        status(f"🖼️  {n} image(s) attached")

    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}]

    last_content = ""
    turn = 0
    try:
        for turn in range(1, MAX_TURNS + 1):
            status(f"🔄 turn {turn}")
            content, tool_calls, finish_reason = call_llm(messages)
            if content:
                last_content = content
            log(f"turn {turn}: content={len(content)}c tools={len(tool_calls)} "
                f"finish={finish_reason}")
            if finish_reason == "length":
                status("⚠️ output truncated (max_tokens) — ответ может быть неполным")
            if VERBOSE and content:
                print(f"\n🤖 {content}")

            if not tool_calls:  # финальный ответ
                if content:
                    if not VERBOSE:
                        print(f"\n{content}")
                else:
                    status("⚠️ finished with empty answer")
                status(f"✅ done in {turn} turns")
                save_result(last_content, "no output" if not last_content else "")
                return 0

            for tc in tool_calls:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                arg_s = json.dumps(args, ensure_ascii=False)
                if VERBOSE:
                    print(f"🔧 {fn}({arg_s})")
                else:
                    status(f"🔧 {fn} {' '.join(arg_s.split())[:60]}")
                log(f"turn {turn} → {fn}({arg_s})")
                result = call_tool(fn, args)
                log(f"turn {turn} ← {fn} [{len(result)}c]\n{result}")
                if VERBOSE:
                    print(f"   → {result[:500]}{'…' if len(result) > 500 else ''}")
                messages.append({"role": "assistant",
                                 "content": content or None,
                                 "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": _clip(result)})

        status(f"⚠️ max turns ({MAX_TURNS}) reached")
        save_result(last_content, f"max turns reached ({MAX_TURNS})")
        return 1
    except KeyboardInterrupt:
        status("⛔ interrupted")
        save_result(last_content, "interrupted")
        return 130
    except Exception as e:
        log(f"FATAL after {turn} turns:\n{traceback.format_exc()}")
        status(f"💥 {type(e).__name__}: {e}")
        save_result(last_content, f"error: {e}")
        return 1


def main() -> int:
    global VERBOSE
    parser = argparse.ArgumentParser(description="LLM coding agent (v2)")
    parser.add_argument("prompt", nargs="?", help="Task description")
    parser.add_argument("-s", "--system-prompt", default=None,
                        help="Custom system prompt")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Full details on stdout")
    args = parser.parse_args()

    if not args.prompt:
        print("No task provided. Exiting.", file=sys.stderr)
        return 1

    VERBOSE = args.verbose
    signal.signal(signal.SIGINT, _on_int)
    start_log()
    try:
        return agent_loop(args.prompt,
                          system_prompt=args.system_prompt or SYSTEM_PROMPT)
    finally:
        stop_log()


if __name__ == "__main__":
    sys.exit(main())
