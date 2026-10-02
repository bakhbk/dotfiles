"""Unit-тесты для loop-детектора в _consume_stream.

Детектор смотрит и на reasoning, и на content. Проверяются четыре сценария:
1. Периодический поток с коротким периодом → срабатывает (finish == "length").
2. Периодический поток с длинным периодом (bash-блок) → срабатывает.
3. Уникальный текст → молчит (finish is None).
4. Короткий текст (< LOOP_WINDOW) → молчит.
"""
import json

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
