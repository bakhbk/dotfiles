"""Unit-тесты для loop-детектора в _consume_stream.

Детектор смотрит и на reasoning, и на content. Проверяются четыре сценария:
1. Периодический поток с коротким периодом → срабатывает (finish == "length").
2. Периодический поток с длинным периодом (bash-блок) → срабатывает.
3. Уникальный текст → молчит (finish is None).
4. Короткий текст (< LOOP_WINDOW) → молчит.
"""
import json

import aigent

# Детерминированные значения, независимо от env
aigent.LOOP_WINDOW = 2000
aigent.LOOP_PROBE = 100
aigent.LOOP_REPEAT = 2


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
    _, _, finish, reasoning, _ = aigent._consume_stream(resp)
    assert finish == "length", (
        f"детектор не сработал: finish={finish}, len(reasoning)={len(reasoning)}"
    )
    assert len(reasoning) < 2500, f"сработал слишком поздно: {len(reasoning)}c"


def test_long_period_fires():
    block = "mkdir -p /tmp/x\n" + ("echo line\n" * 30) + "cd /tmp/x\n"
    text = block * 8
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp)
    assert finish == "length", f"длинный период не пойман: finish={finish}"


def test_unique_quiet():
    text = "".join(f"unique-{i:04d}-line\n" for i in range(100))
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp)
    assert finish is None, f"ложное срабатывание: finish={finish}"


def test_short_quiet():
    text = "short reasoning without any repetition at all."
    resp = _stream(text)
    _, _, finish, _, _ = aigent._consume_stream(resp)
    assert finish is None, f"сработал на коротком вводе: finish={finish}"
