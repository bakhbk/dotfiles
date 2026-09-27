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
