#!/usr/bin/env python3
# Usage: uv run ./aigent.py "hi" [-v] [--provider X --model Y]
#        uv run ./aigent.py --prompt-file prompt.md --provider X --model Y
#        uv run ./aigent.py --prompt-file - --cwd /path/to/project
# /// script
# dependencies = ["requests>=2.31.0", "pyyaml>=6.0"]
# ///
"""LLM coding agent.

- stdout без -v: строки запуска (📄 log-файл, 🔗 provider/url/model) +
  финальный ответ + завершающие статусы (✅ done, 💾 saved, ⚠️/💥 ошибки).
  Промежуточный шум (turn, tool-линии) — только в лог-файл.
- -v: полный вывод (log-путь, endpoint, turn-строки, текст модели, аргументы,
  preview результатов, heartbeat-строки).
- Всё действие асинхронно пишется в $AIGENT_DIR/<ts>-<id>.log (по умолчанию
  ~/.local/state/aigent), путь печатается в stdout на старте.
- Ошибки API: retry x3 (паузы 3/5/10s) на network/429/5xx, 4xx — сразу ошибка.
- Loop-защита включена по умолчанию. Отключение: --no-loop-guard
  или AIGENT_LOOP_GUARD=off.
- Профиль thinking читается из ~/.config/dispatch/model-capabilities.yaml
  (per-model thinking/fallback_thinking, глобальный default_thinking).
  Override: --thinking NAME или AIGENT_THINKING=NAME.
- Exit code: 0 = успех, 1 = ошибка/макс. turn'ов, 3 = пустой ответ LLM, 130 = Ctrl-C.
"""

import argparse
import base64
import configparser
import hashlib
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
import yaml

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PROVIDERS_CONF = os.path.expanduser(
    os.getenv("DISPATCH_PROVIDERS_CONF", "~/.config/dispatch/providers.conf"))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:18080/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "none")


def _load_provider_conf(provider):
    """Вернуть (url, key) для провайдера из dispatch-конфига, иначе (None, None)."""
    if not provider:
        return None, None
    cp = configparser.ConfigParser()
    try:
        if not cp.read(PROVIDERS_CONF):
            return None, None
    except (OSError, configparser.Error):
        return None, None
    if provider not in cp:
        return None, None
    sec = cp[provider]
    url = sec.get("url") or None
    key = sec.get("key") or None
    if key:
        key = key.strip().strip('"').strip("'")
    return url, key

LLM_MODEL = os.getenv("LLM_MODEL", "qwen")
LLM_THINKING = os.getenv("LLM_THINKING", "on")  # on (default) | off — режим рассуждений
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")  # человекочитаемое имя бэкенда для 📄/🔗 строк
LLM_HEADERS = {"Content-Type": "application/json",
               "Authorization": f"Bearer {LLM_API_KEY}"}

MAX_TURNS = int(os.getenv("AIGENT_MAX_TURNS", "50"))
MAX_CONTINUES = 3                # сколько раз «дописывать» ответ при finish=length
MAX_TOKENS = int(os.getenv("AIGENT_MAX_TOKENS", "32768"))  # бюджет вывода за вызов (think+ответ); поднять, если «may be incomplete»
BASH_TIMEOUT = int(os.getenv("AIGENT_BASH_TIMEOUT", "120"))
BASH_MAX_OUTPUT = int(os.getenv("AIGENT_BASH_MAX_OUTPUT", "262144"))  # жёсткий лимит stdout+stderr, байт
LOOP_TIMEOUT = int(os.getenv("AIGENT_LOOP_TIMEOUT", "240"))  # сек без прогресса → форс-финал
LOOP_POLL = 5                                                 # период опроса watchdog, сек
LOOP_WINDOW = int(os.getenv("AIGENT_LOOP_WINDOW", "2000"))    # хвост буфера для поиска повторов, символов
LOOP_PROBE = int(os.getenv("AIGENT_LOOP_PROBE", "100"))       # probe = последние N символов буфера
LOOP_REPEAT = int(os.getenv("AIGENT_LOOP_REPEAT", "2"))       # порог вхождений probe в окне → стоп
LOOP_NORM = re.compile(r"\d+")                                 # инкремент-счётчики → '#'
LOOP_GUARD_ENABLED = os.getenv("AIGENT_LOOP_GUARD", "on").lower() != "off"  # глобальный выключатель
LLM_TIMEOUT = (10, 300)          # (connect, read)
STREAM_STALL = 180               # сек без полезных токенов в стриме = генератор умер
RETRY_DELAYS = (3, 5, 10)        # 3 retry
MAX_TOOL_RESULT = 16_000         # обрезка tool-результата при отправке в LLM

AIGENT_DIR = os.getenv("AIGENT_DIR",
                       os.path.expanduser("~/.local/state/aigent"))
os.makedirs(AIGENT_DIR, exist_ok=True)

DISPATCH_CONFIG_DIR = os.path.expanduser(
    os.getenv("DISPATCH_CONFIG_DIR", "~/.config/dispatch"))
CAPABILITIES_FILE = os.path.join(DISPATCH_CONFIG_DIR, "model-capabilities.yaml")

DEFAULT_CAPABILITIES_YAML = """\
# model-capabilities.yaml
# Вручную поддерживается. Не перезаписывается автоматически.
# Создаётся только если отсутствует.
#
# Своя градация уровней: off < l < h < xh < xxh.
# Для каждой модели — набор level_presets (или свой levels/levels_ref).
# Резолвинг: --thinking → AIGENT_THINKING → models[m].thinking
#   → default_thinking → "l". Если уровня нет у модели — идём вниз
#   по level_order до ближайшего доступного.

level_order: ["off", l, m, h, xh, xxh]

level_presets:
  thinking_5:
    "off":
      think: false
      reasoning: false
      enable_thinking: false
      reasoning_effort: "none"
      chat_template_kwargs: {enable_thinking: false, thinking: false}
      reasoning_config: {enabled: false}
    l:   {enable_thinking: true, reasoning_effort: "low"}
    m:   {enable_thinking: true, reasoning_effort: "medium"}
    h:   {enable_thinking: true, reasoning_effort: "high"}
    xh:  {enable_thinking: true, reasoning_effort: "xhigh"}
    xxh: {enable_thinking: true, reasoning_effort: "xhigh", preserve_thinking: true}
  thinking_3:
    "off":
      think: false
      reasoning: false
      enable_thinking: false
      reasoning_effort: "none"
      chat_template_kwargs: {enable_thinking: false, thinking: false}
      reasoning_config: {enabled: false}
    l:   {enable_thinking: true, reasoning_effort: "low"}
    m:   {enable_thinking: true, reasoning_effort: "medium"}
    h:   {enable_thinking: true, reasoning_effort: "high"}
  onoff:
    "off": {enable_thinking: false}
    l:   {enable_thinking: true}
    m:   {enable_thinking: true}
    h:   {enable_thinking: true}
    xh:  {enable_thinking: true}
    xxh: {enable_thinking: true}

default_levels_ref: thinking_3
default_thinking: l

models: {}
"""

# Хардкод-fallback, если YAML совсем пуст
_FALLBACK_LEVEL = "l"
_FALLBACK_LEVELS: dict = {}

# Заполняются в main() до agent_loop
THINKING_PROFILE: dict = {}
THINKING_PROFILE_NAME: str = ""
LEVEL_ORDER: list = ["off", "l", "m", "h", "xh", "xxh"]


def _ensure_capabilities(auto_yes: bool) -> bool:
    """True — файл есть или создан. False — отказ/нет TTY (caller делает exit 1)."""
    if os.path.exists(CAPABILITIES_FILE):
        return True
    if auto_yes or os.getenv("AIGENT_AUTOCREATE") == "1":
        create = True
    elif not sys.stdin.isatty():
        print(f"{CAPABILITIES_FILE} not found. "
              f"Create it or pass --yes / AIGENT_AUTOCREATE=1.",
              file=sys.stderr)
        return False
    else:
        ans = input(f"{CAPABILITIES_FILE} not found. Create default? [y/N] ").strip().lower()
        create = (ans == "y")
    if not create:
        return False
    os.makedirs(DISPATCH_CONFIG_DIR, exist_ok=True)
    tmp = CAPABILITIES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(DEFAULT_CAPABILITIES_YAML)
    os.replace(tmp, CAPABILITIES_FILE)
    status(f"✅ created: {CAPABILITIES_FILE}")
    return True


def _load_capabilities() -> dict:
    try:
        with open(CAPABILITIES_FILE, encoding="utf-8") as f:
            caps = yaml.safe_load(f) or {}
    except OSError as e:
        status(f"⚠️  cannot read {CAPABILITIES_FILE}: {e}")
        caps = {}
    except yaml.YAMLError as e:
        status(f"⚠️  invalid YAML in {CAPABILITIES_FILE}: {e}")
        caps = {}
    defaults = yaml.safe_load(DEFAULT_CAPABILITIES_YAML)
    # Миграция старого формата: thinking_profiles → level_presets["legacy"]
    if not caps.get("level_presets") and caps.get("thinking_profiles"):
        status(f"⚠️  {CAPABILITIES_FILE}: legacy thinking_profiles, "
               f"treating as level_presets['legacy']")
        caps["level_presets"] = {"legacy": caps["thinking_profiles"]}
        caps.setdefault("default_levels_ref", "legacy")
    if not caps.get("level_presets"):
        caps["level_presets"] = defaults["level_presets"]
        caps.setdefault("default_levels_ref", defaults["default_levels_ref"])
    caps.setdefault("level_order", defaults["level_order"])
    caps.setdefault("default_thinking", defaults["default_thinking"])
    return caps


def _norm_level_key(k):
    """YAML 1.1 парсит off/on как bool; нормализуем обратно в строки."""
    if k is False:
        return "off"
    if k is True:
        return "on"
    return k


def _levels_for_model(model: str, caps: dict) -> dict:
    """Собрать levels для модели: явные → levels_ref → default_levels_ref."""
    models = caps.get("models") or {}
    presets = caps.get("level_presets") or {}
    m = models.get(model) or models.get("*") or {}
    if not isinstance(m, dict):
        m = {}

    levels: dict = {}
    ref = m.get("levels_ref") or caps.get("default_levels_ref")
    if ref and ref in presets:
        for k, v in (presets[ref] or {}).items():
            levels[_norm_level_key(k)] = v

    explicit = m.get("levels")
    if isinstance(explicit, dict):
        for k, v in explicit.items():
            levels[_norm_level_key(k)] = v

    # Override отдельных уровней прямо в модели (top-level, если ключ совпал с уровнем)
    order = caps.get("level_order") or ["off", "l", "m", "h", "xh", "xxh"]
    for lvl in order:
        if lvl in m and isinstance(m[lvl], dict):
            base = levels.get(lvl) or {}
            levels[lvl] = {**base, **m[lvl]}

    return levels


class ThinkingLevelError(ValueError):
    """Неизвестный --thinking уровень."""


def _resolve_level(model: str, explicit: str | None, caps: dict) -> tuple[str, dict]:
    """(level_name, payload). Порядок: explicit → env → model.thinking
    → default_thinking → 'l'. Fallback: вниз по level_order."""
    order = caps.get("level_order") or ["off", "l", "m", "h", "xh", "xxh"]
    if explicit and explicit not in order:
        raise ThinkingLevelError(
            f"unknown --thinking '{explicit}'; valid: {', '.join(order)}")

    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env = os.getenv("AIGENT_THINKING") or os.getenv("LLM_THINKING")
    if env in ("on", "off"):
        if env == "off":
            candidates.append("off")
    elif env:
        candidates.append(env)

    models = caps.get("models") or {}
    m = models.get(model) or models.get("*") or {}
    if isinstance(m, dict) and m.get("thinking"):
        candidates.append(m["thinking"])
    requested = list(candidates)  # explicit/env/model.thinking — без дефолта
    candidates.append(caps.get("default_thinking") or _FALLBACK_LEVEL)
    candidates.append(_FALLBACK_LEVEL)

    levels = _levels_for_model(model, caps)
    if not levels:
        return _FALLBACK_LEVEL, {}

    # Нормализуем кандидатов
    norm_candidates = [_norm_level_key(c) for c in candidates]
    norm_requested = [_norm_level_key(c) for c in requested]

    # Точное совпадение: сначала только запрошенные (без дефолта),
    # иначе дефолт перекроет вниз-fallback по level_order
    for name in norm_requested or norm_candidates:
        if name in levels:
            return name, levels[name]

    # Fallback: вниз по level_order от первого валидного кандидата
    order_idx = {lvl: i for i, lvl in enumerate(order)}
    for name in norm_candidates:
        if name not in order_idx:
            continue
        start = order_idx[name]
        for i in range(start, -1, -1):
            lvl = order[i]
            if lvl in levels:
                return lvl, levels[lvl]

    # Ничего не нашли — берём самый низкий доступный
    for lvl in order:
        if lvl in levels:
            return lvl, levels[lvl]
    return _FALLBACK_LEVEL, {}

SYSTEM_PROMPT = """\
You are a coding agent. Your job is to help the user with programming tasks.

You have access to ONE tool: `bash` — which executes shell commands and returns stdout/stderr.

You have a budget of {max_turns} turns for this task (one turn = one LLM call,
which may include one or more bash calls). Plan accordingly.
- If the task fits in fewer turns, stop as soon as it's done.
- If the task cannot be finished within the budget, deliver a partial result
  with a clear status ("done: ..., remaining: ..., next step: ...") rather
  than running out mid-work.

Workflow:
1. Plan what needs to be done.
2. Use `bash` to read files, run commands, write code, etc.
3. After gathering enough information or completing the task, give your final answer in natural language.
4. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""

BASH_TAIL = """

You have ONE tool: `bash` — it executes shell commands and returns stdout/stderr.
Use it to read/write files and run commands.
Budget: {max_turns} turns. Plan accordingly.

Workflow:
1. If the task requires reading/editing files — do it via `bash`.
2. When the task is done, reply with a regular message (no tool call).

Be concise. Do not explore beyond the task. Do not plan out loud.
"""


NO_TOOLS_TAIL = """

Answer directly. Do not call tools. Do not explore files.
Produce exactly the output format the task specifies. Be concise.
"""


def _compose_system_prompt(custom: str | None, max_turns: int) -> str:
    """system = custom (skill) + tail. Без custom — дефолтный SYSTEM_PROMPT.

    `.replace` вместо `.format`: скиллы содержат JSON-примеры с `{...}`,
    `.format` на них упал бы.
    """
    if NO_TOOLS:
        base = custom.strip() if custom and custom.strip() else ""
        return base + NO_TOOLS_TAIL
    base = custom.strip() if custom and custom.strip() else SYSTEM_PROMPT
    return (base + BASH_TAIL).replace("{max_turns}", str(max_turns))


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
QUIET = False
NO_USAGE = False
NO_TOOLS = False
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
    status(f"📄 log: {LOG_FILE}")  # важно: куда пишется лог — видно всегда


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
    """Короткая строка прогресса: в stdout (если не quiet) + в файл.
    Ошибки (💥 ❌ ⛔ ⚠️) печатаются даже при --quiet."""
    is_error = msg.startswith(("💥", "❌", "⛔", "⚠️"))
    if not QUIET or is_error:
        print(msg, flush=True)
    _log_q.put(msg)


class _HeartbeatHandle:
    """Хэндл для досрочной остановки heartbeat из кода."""

    def __init__(self, stop_event: threading.Event, fired_ref: list):
        self._stop = stop_event
        self._fired = fired_ref

    def stop(self) -> None:
        if VERBOSE and self._fired[0]:
            print("\r" + " " * 72 + "\r", end="", flush=True)
            self._fired[0] = False
        self._stop.set()


@contextmanager
def heartbeat(label: str, interval: int = 10):
    """Пока долгая операция (LLM/bash) идёт: строка в файл каждые N секунд,
    при -v — live-строка в stdout через \\r. Поток просыпается раз в секунду,
    чтобы не задерживать завершение операции.

    Yield: _HeartbeatHandle — можно позвать .stop() досрочно."""
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
        yield _HeartbeatHandle(stop, fired)
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


SSE_LOG_MAX = 500  # максимальная длина сырой строки SSE, попадающей в лог


def _sse_log(raw_line: str, t0: float) -> None:
    """При VERBOSE: писать каждую сырую SSE-строку в лог с таймстампом.
    Длинные строки обрезаются. В stdout не идёт — только в файл."""
    if not VERBOSE:
        return
    el = time.monotonic() - t0
    s = raw_line.strip()
    if len(s) > SSE_LOG_MAX:
        s = s[:SSE_LOG_MAX] + f"… [+{len(s) - SSE_LOG_MAX}c]"
    _log_q.put(f"[sse +{el:6.2f}s] {s}")


def _consume_stream(resp, on_delta=None, on_first_token=None, guard=None):
    """Собирает (content, tool_calls, finish_reason, reasoning, stats) из SSE-чанков.

    Пинги релеи не считаются: если STREAM_STALL секунд нет полезных токенов —
    генератор мертв (relay может держать сокет живым вечно), retryable-ошибка.

    Loop-guard: если последние LOOP_PROBE символов reasoning или content
    встречаются >= LOOP_REPEAT раз в хвосте LOOP_WINDOW символов — стрим
    обрывается с finish="loop" (не "length" — семантика другая). Буфер не
    обрезается: thinking-модель должна видеть свои рассуждения целиком,
    иначе теряет контекст и зацикливается заново. Цифры нормализуются в '#'
    (инкрементирующиеся счётчики не ломают детектор).

    stats: {"ttft": s|None, "tps": tok/s|None, "dur": s,
            "n_chunks": int, "usage": dict|None}
    """
    content, reasoning, finish = "", "", None
    tcs = {}  # index -> tool_call
    t_first = None
    t_last = None
    n_chunks = 0
    usage = None
    last_token = time.monotonic()
    t0 = last_token
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
            _sse_log(line, t0)
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            if not chunk.get("choices"):
                continue
            ch = chunk["choices"][0]
            delta = ch.get("delta") or {}
            meaningful = False
            # первый содержательный чанк — фиксируем TTFT ДО стрима в on_delta
            if (delta.get("reasoning_content") or delta.get("content")
                    or delta.get("tool_calls")) and t_first is None:
                now = time.monotonic()
                t_first = now
                if on_first_token:
                    on_first_token()
                log(f"⏱ first token +{now - t0:.2f}s")
            if delta.get("reasoning_content"):
                rchunk = delta["reasoning_content"]
                reasoning += rchunk
                if on_delta:
                    on_delta("reasoning", rchunk)
                meaningful = True
                if guard is not None and guard.feed("reasoning", rchunk):
                    log("⚠️ reasoning loop in stream, forcing continuation")
                    finish = "loop"
                    break
            if delta.get("content"):
                cchunk = delta["content"]
                content += cchunk
                if on_delta:
                    on_delta("content", cchunk)
                meaningful = True
                if guard is not None and guard.feed("content", cchunk):
                    log("⚠️ content loop in stream, forcing continuation")
                    finish = "loop"
                    break
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
                t_last = time.monotonic()
                n_chunks += 1
                last_token = t_last
    dur = time.monotonic() - t0
    ttft = (t_first - t0) if t_first is not None else None
    gen_dur = (t_last - t_first) if (t_first and t_last and t_last > t_first) else 0.0
    tps = ((n_chunks - 1) / gen_dur) if gen_dur > 0 else None
    ct_total = 0
    if usage:
        ct_total = usage.get("completion_tokens") or 0
    tps_usage = None
    if ct_total and gen_dur > 0:
        tps_usage = ct_total / gen_dur
    stats = {"ttft": ttft, "tps": tps, "tps_usage": tps_usage, "dur": dur,
             "gen_dur": gen_dur, "n_chunks": n_chunks,
             "ct_total": ct_total, "usage": usage}
    return (content.strip(),
            [tcs[i] for i in sorted(tcs)],
            finish,
            reasoning,
            stats)


def call_llm(messages, on_delta=None, guard=None):
    """POST /chat/completions (stream). Возвращает (content, tool_calls, finish_reason, reasoning).

    Retry x3 (3/5/10s) на сетевые ошибки, 429, 5xx. 4xx — сразу LLMError.
    Stream: чанки идут по мере генерации → read-timeout считает паузу между
    чанками, «медленно думает» ≠ «умер» (нет ложных retry).
    """
    payload = {"model": LLM_MODEL, "messages": messages,
               "temperature": 0.1, "max_tokens": MAX_TOKENS,
               "stream": True}
    if not NO_TOOLS:
        payload["tools"] = LLM_TOOLS
        payload["tool_choice"] = "auto"
    if not NO_USAGE:
        payload["stream_options"] = {"include_usage": True}
    if THINKING_PROFILE:
        payload.update(THINKING_PROFILE)
    last_err = ""
    for attempt in range(1 + len(RETRY_DELAYS)):
        if attempt:
            log(f"⚠️ retry {attempt}/{len(RETRY_DELAYS)} in {RETRY_DELAYS[attempt - 1]}s")
            time.sleep(RETRY_DELAYS[attempt - 1])
        resp = None
        try:
            with heartbeat("waiting for first token") as hb:
                resp = requests.post(f"{LLM_BASE_URL}/chat/completions",
                                     json=payload, headers=LLM_HEADERS,
                                     timeout=LLM_TIMEOUT, stream=True)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}",
                                   retryable=True)
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                return _consume_stream(resp, on_delta=on_delta,
                                       on_first_token=hb.stop, guard=guard)
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


def _cap(s: str, limit: int) -> tuple[str, int]:
    """Обрезать строку до limit байт (utf-8). Вернуть (обрезанное, отброшено_байт)."""
    b = s.encode("utf-8", errors="replace")
    if len(b) <= limit:
        return s, 0
    cut = b[:limit].decode("utf-8", errors="replace")
    return cut, len(b) - limit


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
    combined = out + (f"\nSTDERR:\n{err}" if err else "")
    capped, dropped = _cap(combined, BASH_MAX_OUTPUT)
    trailer = (f"\n[... output truncated: {dropped} bytes omitted]"
               if dropped else "")
    return f"Exit code: {p.returncode}\n{capped}{trailer}"


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

def _make_stream_logger(turn):
    """Live-логгер reasoning/content.

    В лог (файл): буферизованные блоки до 800 символов, префикс '💭 '/'🤖 '.
    В stdout при -v: стримится вживую по мере прихода чанков, без обрезки.
    """
    state = {"kind": None, "buf": "",
             "out_kind": None, "out_open": False, "out_ended_nl": False}

    def _pump_out(kind, text):
        """Пишет текст в stdout при -v. На смене kind закрывает строку
        и открывает новую с префиксом '💭 '/'🤖 '. Не добавляет пустую
        строку, если предыдущий вывод уже закончился переводом строки."""
        if not VERBOSE:
            return
        if kind != state["out_kind"]:
            if state["out_open"] and not state["out_ended_nl"]:
                print(flush=True)
            print("\n💭 " if kind == "reasoning" and not state["out_ended_nl"]
                  else ("🤖 " if kind == "content" else "💭 "),
                  end="", flush=True)
            state["out_kind"] = kind
            state["out_open"] = True
        print(text, end="", flush=True)
        state["out_ended_nl"] = text.endswith("\n")

    def emit(kind, chunk):
        if kind != state["kind"]:
            if state["buf"]:
                _log_q.put(state["buf"])
            state["kind"] = kind
            state["buf"] = "💭 " if kind == "reasoning" else "🤖 "
        state["buf"] += chunk
        _pump_out(kind, chunk)
        if len(state["buf"]) > 800 or "\n\n" in chunk or chunk.endswith("\n"):
            _log_q.put(state["buf"])
            state["buf"] = ""

    def flush():
        if state["buf"]:
            _log_q.put(state["buf"])
            state["buf"] = ""
        if state["out_open"]:
            print(flush=True)
            state["out_open"] = False
            state["out_kind"] = None

    return emit, flush


def _merge_stats(a: dict, b: dict) -> dict:
    """Сливает статистику continuation-вызова b в a (in place)."""
    a["n_chunks"] = (a.get("n_chunks") or 0) + (b.get("n_chunks") or 0)
    a["dur"] = (a.get("dur") or 0.0) + (b.get("dur") or 0.0)
    a["gen_dur"] = (a.get("gen_dur") or 0.0) + (b.get("gen_dur") or 0.0)
    a["ct_total"] = (a.get("ct_total") or 0) + (b.get("ct_total") or 0)
    if a.get("ttft") is None and b.get("ttft") is not None:
        a["ttft"] = b["ttft"]
    if b.get("usage"):
        a["usage"] = b["usage"]
    gd = a["gen_dur"]
    a["tps"] = ((a["n_chunks"] - 1) / gd) if gd > 0 else None
    a["tps_usage"] = (a["ct_total"] / gd) if (a["ct_total"] and gd > 0) else None
    return a


class LoopGuard:
    """Порт loop-защиты: стрим-детектор + watchdog уровня turn.

    Единственная точка управления. enabled=False → все методы no-op,
    буферы не аккумулируются, watchdog не стартует, stuck всегда False.

    Стрим-детектор: feed(label, chunk) копит последние window символов
    reasoning/content и возвращает True, если probe (хвост из probe
    символов с нормализованными цифрами) встречается >= repeat раз в
    окне. Тогда _consume_stream ставит finish="loop" и выходит из стрима.

    Watchdog: поток ждёт poll сек, выставляет stuck, если сигнатура
    (tool_calls, content, reasoning) не менялась watchdog_timeout сек.
    """
    def __init__(self, enabled=True, window=None, probe=None, repeat=None,
                 watchdog_timeout=None, poll=None):
        self.enabled = enabled
        self.window = window if window is not None else LOOP_WINDOW
        self.probe = probe if probe is not None else LOOP_PROBE
        self.repeat = repeat if repeat is not None else LOOP_REPEAT
        self.watchdog_timeout = (watchdog_timeout if watchdog_timeout is not None
                                 else LOOP_TIMEOUT)
        self.poll = poll if poll is not None else LOOP_POLL
        self._rbuf = ""
        self._cbuf = ""
        self._stuck = threading.Event()
        self._sig = None
        self._last_change = time.monotonic()
        self._stop = threading.Event()
        self._th = None

    def feed(self, label, chunk):
        """True → зацикливание в стриме (reasoning или content)."""
        if not self.enabled:
            return False
        if label == "reasoning":
            self._rbuf = (self._rbuf + chunk)[-self.window:]
            buf = self._rbuf
        else:
            self._cbuf = (self._cbuf + chunk)[-self.window:]
            buf = self._cbuf
        if len(buf) < self.window:
            return False
        probe = LOOP_NORM.sub("#", buf[-self.probe:])
        window = LOOP_NORM.sub("#", buf)
        return bool(probe) and window.count(probe) >= self.repeat

    def start(self):
        if not self.enabled:
            return
        self._th = threading.Thread(target=self._watch, daemon=True)
        self._th.start()

    def stop(self):
        if not self.enabled or self._th is None:
            return
        self._stop.set()
        self._th.join(timeout=5)

    def touch(self, tool_calls, content, reasoning=""):
        if not self.enabled:
            return
        sig = hashlib.md5(
            (repr([(tc["function"]["name"], tc["function"]["arguments"])
                   for tc in tool_calls])[:2000]
             + (content or "")[:2000]
             + (reasoning or "")[:2000]).encode(),
            usedforsecurity=False,
        ).hexdigest()
        if sig != self._sig:
            self._sig = sig
            self._last_change = time.monotonic()

    def reset(self):
        """Сброс окна наблюдения после nudge. Перезапускает _watch."""
        if not self.enabled:
            return
        self._stop.set()
        if self._th is not None:
            self._th.join(timeout=1)
        self._sig = None
        self._last_change = time.monotonic()
        self._stuck.clear()
        self._stop.clear()
        self._th = threading.Thread(target=self._watch, daemon=True)
        self._th.start()

    def _watch(self):
        while not self._stop.wait(self.poll):
            if self._stuck.is_set():
                return
            if time.monotonic() - self._last_change > self.watchdog_timeout:
                self._stuck.set()
                return

    @property
    def stuck(self):
        return self.enabled and self._stuck.is_set()

    def nudge(self, finish_reason):
        if finish_reason == "loop":
            return ("Ты повторяешься. Не продолжай ту же мысль — "
                    "переходи к финальному ответу.")
        if finish_reason == "length":
            return ("Продолжи с места, где остановился. "
                    "Не повторяй уже написанное.")
        return ""


def agent_loop(user_message: str, system_prompt: str = SYSTEM_PROMPT) -> int:
    log(f"🔗 provider={LLM_PROVIDER} {LLM_BASE_URL} model={LLM_MODEL}")
    log(f"prompt: {user_message}")

    user_content = build_user_content(user_message)
    if isinstance(user_content, list):
        n = sum(1 for c in user_content if c.get("type") == "image_url")
        log(f"🖼️  {n} image(s) attached")

    system_content = _compose_system_prompt(system_prompt, MAX_TURNS)
    messages = [{"role": "system", "content": system_content},
                {"role": "user", "content": user_content}]

    last_content = ""
    guard = LoopGuard(enabled=LOOP_GUARD_ENABLED)
    guard.start()
    guard.touch([], "")
    nudged = False
    _empty_nudged = False
    turn = 0
    turns_stats = []
    try:
        for turn in range(1, MAX_TURNS + 1):
            if guard.stuck and not nudged:
                status("🔁 no progress → asking for final answer")
                log("🔁 watchdog fired: injecting nudge")
                messages.append({"role": "user",
                                 "content": "No progress detected — you are repeating "
                                            "the same reasoning. Stop the current line "
                                            "and proceed to the next concrete step."})
                nudged = True
                guard.reset()
            elif guard.stuck and nudged:
                status("🔁 loop persists after nudge → abort")
                save_result(last_content, "loop detected")
                return 1
            log(f"───── turn {turn} ─────")
            emit, flush = _make_stream_logger(turn)
            try:
                content, tool_calls, finish_reason, reasoning, stats = call_llm(
                    messages, on_delta=emit, guard=guard)
            finally:
                flush()
            if finish_reason in ("length", "loop"):
                # "length": модель не уложилась в max_tokens — просим продолжить.
                # "loop": loop-guard поймал петлю в стриме — просим модель
                #         не продолжать ту же мысль, перейти к финальному ответу.
                full = content
                cont = 0
                while finish_reason in ("length", "loop") and cont < MAX_CONTINUES:
                    cont += 1
                    reason = finish_reason
                    log(f"turn {turn}: finish={reason} → continuation {cont}/{MAX_CONTINUES}")
                    am = {"role": "assistant", "content": content}
                    if reasoning:
                        am["reasoning_content"] = reasoning
                    messages.append(am)
                    messages.append({"role": "user", "content": guard.nudge(reason)})
                    content, tool_calls, finish_reason, reasoning, _stats = call_llm(
                        messages, guard=guard)
                    _merge_stats(stats, _stats)
                    log(f"turn {turn}: continuation {cont}: content={len(content)}c "
                        f"finish={finish_reason}")
                    full = (full or "") + (content or "")
                content = full
                if finish_reason in ("length", "loop"):
                    log(f"⚠️ answer may be incomplete (still {finish_reason} after continuations)")
            turns_stats.append(stats)
            ttft = stats.get("ttft")
            tps = stats.get("tps")
            tps_usage = stats.get("tps_usage")
            dur = stats.get("dur") or 0.0
            ttft_s = f"{ttft:.2f}s" if ttft is not None else "-"
            tps_s = f"{tps:.1f}" if tps is not None else "-"
            tps_usage_s = f"/{tps_usage:.1f}u" if tps_usage is not None else ""
            usage_note = ""
            u = stats.get("usage")
            if u:
                pt = u.get("prompt_tokens")
                ct = u.get("completion_tokens")
                if pt is not None and ct is not None:
                    usage_note = f" usage={pt}+{ct}"
            status(f"turn {turn}: ttft={ttft_s} tps={tps_s}{tps_usage_s} "
                   f"finish={finish_reason} content={len(content)}c "
                   f"reasoning={len(reasoning)}c tools={len(tool_calls)} "
                   f"dur={dur:.2f}s{usage_note}")
            if content:
                last_content = content

            if not tool_calls:  # финальный ответ
                if content:
                    if not VERBOSE:
                        print(f"\n{content}")
                    ttfts = [s["ttft"] for s in turns_stats if s["ttft"] is not None]
                    tpss = [s["tps"] for s in turns_stats if s["tps"] is not None]
                    tpsu = [s.get("tps_usage") for s in turns_stats if s.get("tps_usage")]
                    total_dur = sum((s.get("dur") or 0.0) for s in turns_stats)
                    parts = [f"✅ done in {turn} turns"]
                    if ttfts:
                        parts.append(f"avg ttft={sum(ttfts) / len(ttfts):.2f}s")
                    if tpss:
                        parts.append(f"avg tps={sum(tpss) / len(tpss):.1f}")
                    if tpsu:
                        parts.append(f"avg tps_usage={sum(tpsu) / len(tpsu):.1f}")
                    parts.append(f"total dur={total_dur:.2f}s")
                    last_usage = turns_stats[-1].get("usage") if turns_stats else None
                    if last_usage:
                        pt = last_usage.get("prompt_tokens")
                        ct = last_usage.get("completion_tokens")
                        if pt is not None and ct is not None:
                            parts.append(f"usage={pt}+{ct}")
                    print(flush=True)
                    status(" — ".join(parts))
                    save_result(last_content, "no output" if not last_content else "")
                    return 0
                # пустой финальный ответ
                if not _empty_nudged:
                    status("⚠️ empty answer, retrying once with nudge")
                    if messages and messages[-1].get("role") == "user":
                        messages.append({"role": "assistant", "content": ""})
                    if NO_TOOLS:
                        nudge = ("Ты не дал ответа. Верни финальный ответ "
                                 "текстом строго по формату из промпта.")
                    else:
                        nudge = ("Продолжи работу: выполни оставшиеся шаги "
                                 "через инструменты (bash), затем верни "
                                 "короткий финальный отчёт.")
                    messages.append({"role": "user", "content": nudge})
                    _empty_nudged = True
                    continue
                status("⚠️ finished with empty answer")
                reason = ("empty answer" if not last_content
                          else "empty answer after nudge")
                save_result(last_content, reason)
                return 3

            messages.append({"role": "assistant",
                             "content": content or None,
                             "tool_calls": tool_calls})
            for tc in tool_calls:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                arg_s = json.dumps(args, ensure_ascii=False)
                # в stdout — только при -v (полные аргументы), иначе — в файл
                log(f"🔧 {fn}({arg_s})")
                result = call_tool(fn, args)
                log(f"turn {turn} ← {fn} [{len(result)}c]\n{result}")
                if VERBOSE:
                    print(f"   → {result[:500]}{'…' if len(result) > 500 else ''}")
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": _clip(result)})
            guard.touch(tool_calls, content, reasoning)

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
    finally:
        guard.stop()


def main() -> int:
    global VERBOSE, QUIET, NO_USAGE, NO_TOOLS, LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, MAX_TURNS, MAX_TOKENS, LLM_THINKING, LOOP_GUARD_ENABLED, THINKING_PROFILE, THINKING_PROFILE_NAME, LEVEL_ORDER
    parser = argparse.ArgumentParser(description="LLM coding agent (v2)")
    parser.add_argument("prompt", nargs="?", help="Task description")
    parser.add_argument("-s", "--system-prompt", default=None,
                        help="Custom system prompt (string)")
    parser.add_argument("--system-prompt-file", default=None,
                        help="Read system prompt from file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Full details on stdout")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Silence progress on stdout (log still written)")
    parser.add_argument("--no-usage", action="store_true",
                        help="Do not request stream usage (for backends that "
                             "reject stream_options)")
    parser.add_argument("--no-tools", action="store_true",
                        help="Do not offer bash tool (verdict-only roles)")
    parser.add_argument("--provider", default=None,
                        help="Override LLM_PROVIDER (label for 📄/🔗)")
    parser.add_argument("--model", default=None,
                        help="Override LLM_MODEL")
    parser.add_argument("--base-url", default=None,
                        help="Override LLM_BASE_URL")
    parser.add_argument("--prompt-file", default=None,
                        help="Read task from file (use - for stdin)")
    parser.add_argument("--max-turns", type=int, default=None,
                        help=f"Override MAX_TURNS (default: {MAX_TURNS})")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help=f"Override MAX_TOKENS (default: {MAX_TOKENS})")
    parser.add_argument("--no-thinking", action="store_true",
                        help="Alias for --thinking off")
    parser.add_argument("--thinking", default=None,
                        help="Thinking level: off|l|h|xh|xxh (default: per-model from YAML)")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Auto-create model-capabilities.yaml if missing")
    parser.add_argument("--no-loop-guard", action="store_true",
                        help="Disable loop-guard and watchdog entirely")
    parser.add_argument("--cwd", default=None,
                        help="Working directory for bash tool (default: current)")
    args = parser.parse_args()

    if args.provider:
        LLM_PROVIDER = args.provider
    if args.model:
        LLM_MODEL = args.model
    if args.base_url:
        LLM_BASE_URL = args.base_url
    if args.max_turns:
        MAX_TURNS = args.max_turns
    if args.max_tokens:
        MAX_TOKENS = args.max_tokens
    if args.no_thinking:
        args.thinking = "off"
    if args.no_loop_guard:
        LOOP_GUARD_ENABLED = False
    if args.cwd:
        cwd = os.path.expanduser(args.cwd)
        if not os.path.isdir(cwd):
            print(f"cwd not a directory: {cwd}", file=sys.stderr)
            return 1
        os.chdir(cwd)

    if args.prompt_file:
        if args.prompt_file == "-":
            task_text = sys.stdin.read()
        else:
            with open(args.prompt_file, encoding="utf-8") as f:
                task_text = f.read()
    else:
        task_text = args.prompt

    if not task_text:
        print("No task provided. Exiting.", file=sys.stderr)
        return 1

    VERBOSE = args.verbose
    QUIET = args.quiet
    NO_USAGE = args.no_usage
    NO_TOOLS = args.no_tools

    # Порядок приоритетов: env-переменные > секция [provider] в dispatch.conf > дефолты
    if not os.environ.get("LLM_BASE_URL") or not os.environ.get("LLM_API_KEY"):
        url, key = _load_provider_conf(LLM_PROVIDER)
        if not os.environ.get("LLM_BASE_URL") and url:
            LLM_BASE_URL = url
        if not os.environ.get("LLM_API_KEY") and key:
            LLM_API_KEY = key
        LLM_HEADERS["Authorization"] = f"Bearer {LLM_API_KEY}"

    system_prompt = args.system_prompt
    if args.system_prompt_file:
        with open(args.system_prompt_file, encoding="utf-8") as f:
            system_prompt = f.read()

    if not _ensure_capabilities(auto_yes=args.yes):
        return 1
    caps = _load_capabilities()
    LEVEL_ORDER = caps.get("level_order") or LEVEL_ORDER
    try:
        THINKING_PROFILE_NAME, THINKING_PROFILE = _resolve_level(
            LLM_MODEL, args.thinking, caps)
    except ThinkingLevelError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    status(f"🧠 thinking: {THINKING_PROFILE_NAME} (model={LLM_MODEL})")

    signal.signal(signal.SIGINT, _on_int)
    start_log()
    try:
        return agent_loop(task_text, system_prompt=system_prompt)
    finally:
        stop_log()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⛔ interrupted", file=sys.stderr)
        sys.exit(130)
