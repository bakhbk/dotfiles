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
LLM_THINKING = os.getenv("LLM_THINKING", "on")  # on (default) | off — режим рассуждений
LLM_HEADERS = {"Content-Type": "application/json",
               "Authorization": f"Bearer {LLM_API_KEY}"}

MAX_TURNS = 1000
MAX_CONTINUES = 3                # сколько раз «дописывать» ответ при finish=length
MAX_TOKENS = int(os.getenv("AIGENT_MAX_TOKENS", "16384"))  # бюджет вывода за вызов (think+ответ); поднять, если «may be incomplete»
BASH_TIMEOUT = 120
LLM_TIMEOUT = (10, 300)          # (connect, read)
STREAM_STALL = 180               # сек без полезных токенов в стриме = генератор умер
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


def _consume_stream(resp):
    """Собирает (content, tool_calls, finish_reason, reasoning) из SSE-чанков.

    Пинги релеи не считаются: если STREAM_STALL секунд нет полезных токенов —
    генератор мертв (relay может держать сокет живым вечно), retryable-ошибка.
    """
    content, reasoning, finish = "", "", None
    tcs = {}  # index -> tool_call
    last_token = time.monotonic()
    with resp:
        for raw in resp.iter_lines():
            if time.monotonic() - last_token > STREAM_STALL:
                raise LLMError(f"stream stalled: no tokens for {STREAM_STALL}s",
                               retryable=True)
            if not raw:
                continue
            line = raw.decode() if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if not chunk.get("choices"):
                continue
            ch = chunk["choices"][0]
            delta = ch.get("delta") or {}
            meaningful = False
            if delta.get("reasoning_content"):
                reasoning += delta["reasoning_content"]
                meaningful = True
            if delta.get("content"):
                content += delta["content"]
                meaningful = True
            for d in delta.get("tool_calls") or []:
                tc = tcs.setdefault(d.get("index", 0),
                                    {"id": "", "type": "function",
                                     "function": {"name": "", "arguments": ""}})
                if d.get("id"):
                    tc["id"] = d["id"]
                fn = d.get("function") or {}
                if fn.get("name"):
                    tc["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    tc["function"]["arguments"] += fn["arguments"]
                    meaningful = True
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
                meaningful = True
            if meaningful:
                last_token = time.monotonic()
    return (content.strip(),
            [tcs[i] for i in sorted(tcs)],
            finish,
            reasoning)


def call_llm(messages):
    """POST /chat/completions (stream). Возвращает (content, tool_calls, finish_reason, reasoning).

    Retry x3 (3/5/10s) на сетевые ошибки, 429, 5xx. 4xx — сразу LLMError.
    Stream: чанки идут по мере генерации → read-timeout считает паузу между
    чанками, «медленно думает» ≠ «умер» (нет ложных retry).
    """
    payload = {"model": LLM_MODEL, "messages": messages, "tools": LLM_TOOLS,
               "tool_choice": "auto", "temperature": 0.1, "max_tokens": MAX_TOKENS,
               "stream": True}
    if LLM_THINKING == "off":
        # «дробовик»: все известные диалекты off (как в doit.sh) — провайдеры
        # понимают только свои флаги, остальные игнорируют.
        payload.update(think=False, reasoning=False, enable_thinking=False,
                       reasoning_effort="none",
                       chat_template_kwargs={"enable_thinking": False, "thinking": False},
                       reasoning_config={"enabled": False})
    last_err = ""
    for attempt in range(1 + len(RETRY_DELAYS)):
        if attempt:
            log(f"⚠️ retry {attempt}/{len(RETRY_DELAYS)} in {RETRY_DELAYS[attempt - 1]}s")
            time.sleep(RETRY_DELAYS[attempt - 1])
        resp = None
        try:
            with heartbeat("LLM call"):
                resp = requests.post(f"{LLM_BASE_URL}/chat/completions",
                                     json=payload, headers=LLM_HEADERS,
                                     timeout=LLM_TIMEOUT, stream=True)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}",
                                   retryable=True)
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                return _consume_stream(resp)
        except LLMError as e:
            last_err = str(e)
            if not e.retryable:
                raise
        except (requests.RequestException, ValueError, KeyError) as e:
            last_err = f"{type(e).__name__}: {e}"
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
        log(f"⚠️ attempt {attempt + 1} failed: {last_err}")
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
            content, tool_calls, finish_reason, reasoning = call_llm(messages)
            if reasoning:
                log(f"turn {turn} 💭 {len(reasoning)}c\n{reasoning}")
                if VERBOSE:
                    print(f"\n💭 …{reasoning[-500:]}")
            log(f"turn {turn}: content={len(content)}c tools={len(tool_calls)} "
                f"finish={finish_reason}")
            if finish_reason == "length":
                # Бюджет выгорел (типично для reasoning-моделей: think съел весь max_tokens).
                # Дожимаем: просим продолжить, пока модель не закончит сама.
                full = content
                cont = 0
                while finish_reason == "length" and cont < MAX_CONTINUES:
                    cont += 1
                    log(f"turn {turn}: finish=length → continuation {cont}/{MAX_CONTINUES}")
                    am = {"role": "assistant", "content": content}
                    if reasoning:
                        am["reasoning_content"] = reasoning
                    messages.append(am)
                    messages.append({"role": "user",
                                     "content": "Продолжи с места, где остановился. "
                                                "Не повторяй уже написанное."})
                    content, tool_calls, finish_reason, reasoning = call_llm(messages)
                    log(f"turn {turn}: continuation {cont}: content={len(content)}c "
                        f"finish={finish_reason}")
                    full = (full or "") + (content or "")
                content = full
                if finish_reason == "length":
                    log("⚠️ answer may be incomplete (still truncated after continuations)")
            if content:
                last_content = content
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
