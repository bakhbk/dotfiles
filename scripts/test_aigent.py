# Usage: uv run --with pytest pytest ./scripts/test_aigent.py -q
"""Unit-тесты для loop-детектора в _consume_stream.

Детектор смотрит и на reasoning, и на content. Проверяются четыре сценария:
1. Периодический поток с коротким периодом → срабатывает (finish == "length").
2. Периодический поток с длинным периодом (bash-блок) → срабатывает.
3. Уникальный текст → молчит (finish is None).
4. Короткий текст (< LOOP_WINDOW) → молчит.
"""
import json
import os

import aigent

def _guard():
    return aigent.LoopGuard(enabled=True, window=2000, probe=100, repeat=2)


CAPS_FIXTURE = {
    "level_order": ["off", "l", "m", "h", "xh", "xxh"],
    "level_presets": {
        "thinking_5": {
            "off": {"think": False, "enable_thinking": False,
                    "reasoning_effort": "none"},
            "l":   {"enable_thinking": True, "reasoning_effort": "low"},
            "h":   {"enable_thinking": True, "reasoning_effort": "high"},
            "xh":  {"enable_thinking": True, "reasoning_effort": "xhigh"},
            "xxh": {"enable_thinking": True, "reasoning_effort": "xhigh",
                    "preserve_thinking": True},
        },
        "thinking_3": {
            "off": {"think": False, "enable_thinking": False},
            "l":   {"enable_thinking": True, "reasoning_effort": "low"},
            "m":   {"enable_thinking": True, "reasoning_effort": "medium"},
            "h":   {"enable_thinking": True, "reasoning_effort": "high"},
        },
    },
    "default_levels_ref": "thinking_3",
    "default_thinking": "l",
    "models": {
        "qwen3.8-27b": {"levels_ref": "thinking_5"},
        "qwen3.6-35b": {"levels_ref": "thinking_3"},
        "custom": {
            "levels_ref": "thinking_3",
            "xh": {"enable_thinking": True, "reasoning_effort": "xhigh"},
        },
    },
}


def test_resolve_exact():
    name, payload = aigent._resolve_level("qwen3.8-27b", "xh", CAPS_FIXTURE)
    assert name == "xh"
    assert payload["reasoning_effort"] == "xhigh"


def test_resolve_fallback_down():
    # thinking_3 не имеет xh — должен откатиться на h
    name, payload = aigent._resolve_level("qwen3.6-35b", "xh", CAPS_FIXTURE)
    assert name == "h"
    assert payload["reasoning_effort"] == "high"


def test_resolve_xxh_fallback_to_xh():
    # thinking_5 имеет xxh, но если бы не было — упало бы на xh
    name, _ = aigent._resolve_level("qwen3.8-27b", "xxh", CAPS_FIXTURE)
    assert name == "xxh"


def test_resolve_override_merges():
    # custom: levels_ref=thinking_3 (нет xh) + top-level override xh
    name, payload = aigent._resolve_level("custom", "xh", CAPS_FIXTURE)
    assert name == "xh"
    assert payload["reasoning_effort"] == "xhigh"


def test_resolve_default_when_no_explicit():
    name, _ = aigent._resolve_level("qwen3.6-35b", None, CAPS_FIXTURE)
    assert name == "l"


def test_resolve_unknown_model_falls_back():
    name, payload = aigent._resolve_level("nope", "xxh", CAPS_FIXTURE)
    # default_levels_ref=thinking_3, xxh нет → вниз до h
    assert name == "h"


def test_resolve_off():
    name, payload = aigent._resolve_level("qwen3.8-27b", "off", CAPS_FIXTURE)
    assert name == "off"
    assert payload["enable_thinking"] is False


def test_resolve_m_level():
    name, payload = aigent._resolve_level("qwen3.6-35b", "m", CAPS_FIXTURE)
    assert name == "m"
    assert payload["reasoning_effort"] == "medium"


def test_resolve_unknown_level_raises():
    import pytest as _pt
    with _pt.raises(aigent.ThinkingLevelError):
        aigent._resolve_level("qwen3.8-27b", "xxl", CAPS_FIXTURE)
    with _pt.raises(aigent.ThinkingLevelError):
        aigent._resolve_level("qwen3.8-27b", "offf", CAPS_FIXTURE)


def _tc(name, args):
    return {"function": {"name": name, "arguments": args}}


def test_feed_tool_repeats_fires():
    g = aigent.LoopGuard(enabled=True)
    same = [_tc("bash", '{"command":"ls"}')]
    assert g.feed_tool(same) is False   # 1-й
    assert g.feed_tool(same) is False   # 2-й
    assert g.feed_tool(same) is True    # 3-й → петля


def test_feed_tool_different_no_fire():
    g = aigent.LoopGuard(enabled=True)
    assert g.feed_tool([_tc("bash", '{"command":"ls"}')]) is False
    assert g.feed_tool([_tc("bash", '{"command":"cat x"}')]) is False
    assert g.feed_tool([_tc("bash", '{"command":"pwd"}')]) is False


def test_touch_repeat_marks_stuck():
    g = aigent.LoopGuard(enabled=True)
    tc = [_tc("bash", '{"command":"ls"}')]
    for _ in range(aigent.WATCHDOG_REPEAT_LIMIT):
        g.touch(tc, "", "")
    assert g.stuck is True


def test_touch_disabled_no_stuck():
    g = aigent.LoopGuard(enabled=False)
    tc = [_tc("bash", '{"command":"ls"}')]
    for _ in range(10):
        g.touch(tc, "", "")
    assert g.stuck is False
    assert g.feed_tool(tc) is False


class FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        for line in self._lines:
            yield line


def _stream(reasoning_text, chunk=10):
    lines = []
    for i in range(0, len(reasoning_text), chunk):
        d = {"choices": [{"delta": {"reasoning_content": reasoning_text[i:i + chunk]}}]}
        lines.append("data: " + json.dumps(d))
    lines.append("data: [DONE]")
    return FakeResp(lines)


def test_periodic_fires():
    phrase = "One detail: I need to check if validate_manifest.py is available.\n"
    text = phrase * 40
    resp = _stream(text)
    _, _, finish, reasoning, _ = aigent._consume_stream(resp, guard=_guard())
    assert finish == "loop", (
        f"детектор не сработал: finish={finish}, len(reasoning)={len(reasoning)}"
    )
    assert len(reasoning) < 2500, f"сработал слишком поздно: {len(reasoning)}c"


def test_long_period_fires():
    block = "mkdir -p /tmp/x\n" + ("echo line\n" * 30) + "cd /tmp/x\n"
    text = block * 8
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp, guard=_guard())
    assert finish == "loop", f"длинный период не пойман: finish={finish}"


def test_unique_quiet():
    text = "".join(f"unique-{i:04d}-line\n" for i in range(100))
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp, guard=_guard())
    assert finish is None, f"ложное срабатывание: finish={finish}"


def test_short_quiet():
    text = "short reasoning without any repetition at all."
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp, guard=_guard())
    assert finish is None, f"сработал на коротком вводе: finish={finish}"


def test_counter_period_fires():
    lines = [
        "все требования задачи выполнены, манифест и промты готовы",
        "финальный ответ: ✅ manifest.txt: 3 волн, 3 задач, score=100/100",
        "задача завершена, декомпозиция выполнена",
        "все файлы на месте, валидация пройдена, score 100/100",
        "готово к исполнению агентами по волнам",
    ]
    text = "".join(
        f"- **Примечание {i}**: {lines[i % len(lines)]}\n\n"
        for i in range(1, 200)
    )
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp, guard=_guard())
    assert finish == "loop", f"инкремент-счётчик не пойман: finish={finish}"


def test_empty_answer_exit_3(monkeypatch):
    """agent_loop с пустым content и без tool_calls → exit 3."""
    # Заглушка call_llm: возвращает ("", [], None, "", {}) — пусто
    calls = {"n": 0}
    def fake_call_llm(messages, on_delta=None, guard=None):
        calls["n"] += 1
        return "", [], None, "", {}
    monkeypatch.setattr(aigent, "call_llm", fake_call_llm)
    monkeypatch.setattr(aigent, "save_result", lambda *a, **k: None)
    rc = aigent.agent_loop("test")
    assert rc == 3, f"ожидался exit 3, получен {rc}, вызовов call_llm={calls['n']}"


CONF = "[Jarvis]\nurl=https://jarvis.example/v1\nkey=sk-j\n\n[kr-jarvis]\nurl=http://localhost:18085/v1\nkey=sk-k\n"


def _conf(tmp_path, monkeypatch):
    path = tmp_path / "providers.conf"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(aigent, "PROVIDERS_CONF", str(path))
    return path


def test_provider_lookup_ignores_case(tmp_path, monkeypatch):
    _conf(tmp_path, monkeypatch)
    assert aigent._load_provider_conf("jarvis") == ("https://jarvis.example/v1", "sk-j")
    assert aigent._load_provider_conf("nope") == (None, None)


def test_explicit_provider_beats_env(tmp_path, monkeypatch):
    _conf(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:18085/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-k")
    assert aigent._resolve_llm_config("Jarvis", True) == ("https://jarvis.example/v1", "sk-j")


def test_env_kept_when_provider_implicit(tmp_path, monkeypatch):
    _conf(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:18085/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-k")
    assert aigent._resolve_llm_config("local", False) == ("http://localhost:18085/v1", "sk-k")


def test_base_url_wins(tmp_path, monkeypatch):
    _conf(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:18085/v1")
    url, key = aigent._resolve_llm_config("Jarvis", True, "http://127.0.0.1:1234/v1")
    assert (url, key) == ("http://127.0.0.1:1234/v1", "sk-j")


def test_ttft_includes_queue_wait():
    import time
    resp = _stream("hello world", chunk=5)
    t0 = time.monotonic() - 5.0
    *_, stats = aigent._consume_stream(resp, t0=t0)
    assert stats["ttft"] >= 5.0, f"очередь не учтена: ttft={stats['ttft']}"
    assert stats["dur"] >= 5.0 and stats["wait"] >= 0.0
    assert stats["gen_dur"] < stats["ttft"]


def test_ttft_without_t0():
    *_, stats = aigent._consume_stream(_stream("hello world", chunk=5))
    assert stats["ttft"] is not None and stats["wait"] >= 0.0


def test_call_llm_measures_queue_wait(monkeypatch):
    """Regression: ttft/wait считаются от отправки POST, а не от заголовков."""
    import time

    class QueuedResp(FakeResp):
        status_code = 200

        def __init__(self, lines, delay):
            super().__init__(lines)
            time.sleep(delay)

        def close(self):
            pass

    monkeypatch.setattr(aigent.requests, "post",
                        lambda url, **kw: QueuedResp(["data: [DONE]"], 0.3))
    *_, stats = aigent.call_llm([{"role": "user", "content": "hi"}])
    assert stats["wait"] >= 0.3, f"очередь потеряна: wait={stats['wait']}"
    assert stats["ttft"] is None, f"пустой стрим не должен давать ttft: {stats['ttft']}"


def test_timing_line_hides_duplicate_wait():
    stats = {"ttft": 198.5, "wait": 198.5, "gen_dur": 1.98, "dur": 200.48}
    assert aigent._timing_line(stats) == "ttft=198.50s gen=1.98s dur=200.48s"


def test_timing_line_shows_real_wait_phase():
    stats = {"ttft": 30.0, "wait": 0.2, "gen_dur": 29.8, "dur": 30.0}
    assert aigent._timing_line(stats) == "ttft=30.00s wait=0.20s gen=29.80s dur=30.00s"


def test_timing_line_without_first_token():
    assert "ttft=-" in aigent._timing_line({"wait": 5.0, "dur": 5.0})


def test_summary_counts_tool_calls():
    turns_stats = [{"ttft": 1.0, "dur": 2.0, "tools": 2},
                   {"ttft": 0.5, "dur": 1.0, "tools": 0}]
    s = aigent._summary(turns_stats)
    assert "tools=2" in s
    assert "total dur=3.00s" in s
    assert "done in 2 turns" in s


def test_live_overwrites_previous_line(capsys):
    aigent._live_len[0] = 0
    aigent.live("turn 1: dur=1.2s")
    aigent.live("turn 2: dur=2.7s")
    out = capsys.readouterr().out
    assert out == "\r\rturn 1: dur=1.2s\r" + " " * 16 + "\rturn 2: dur=2.7s"
    assert aigent._live_len[0] == 16


def test_live_is_silent_when_quiet(capsys):
    aigent.QUIET, saved = True, aigent.QUIET
    try:
        aigent._live_len[0] = 0
        aigent.live("turn 1")
        assert capsys.readouterr().out == ""
        assert aigent._live_len[0] == 0
    finally:
        aigent.QUIET = saved


def test_live_truncates_to_terminal_width(capsys):
    saved = aigent.shutil.get_terminal_size
    aigent.shutil.get_terminal_size = lambda: os.terminal_size((80, 24))
    try:
        aigent._live_len[0] = 0
        aigent.live("x" * 500)
        out = capsys.readouterr().out
        assert len(out) == 1 + 79 + 1
        assert aigent._live_len[0] == 79
    finally:
        aigent.shutil.get_terminal_size = saved


def test_clear_live_resets_state(capsys):
    aigent._live_len[0] = 5
    aigent.clear_live()
    assert capsys.readouterr().out == "\r" + " " * 5 + "\r"
    assert aigent._live_len[0] == 0
    aigent.clear_live()
    assert capsys.readouterr().out == ""


def test_status_keeps_last_live_line(capsys):
    aigent._live_len[0] = 0
    aigent.live("turn 7: dur=3.4s")
    aigent.status("✅ done in 7 turns")
    out = capsys.readouterr().out
    assert out == "\r\rturn 7: dur=3.4s\n✅ done in 7 turns\n"
    assert aigent._live_len[0] == 0


def test_llm_stream_requests_close_connection(monkeypatch):
    captured = {}

    class OkResp(FakeResp):
        status_code = 200

        def close(self):
            pass

    def fake_post(url, **kw):
        captured["headers"] = kw.get("headers") or {}
        return OkResp(["data: [DONE]"])

    monkeypatch.setattr(aigent.requests, "post", fake_post)
    aigent.call_llm([{"role": "user", "content": "hi"}])
    assert captured["headers"].get("Connection") == "close", (
        "SSE keep-alive leaves the proxy waiting for EOF: it logs the "
        "completed answer as 499 (client hangup)"
    )
