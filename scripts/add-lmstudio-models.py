#!/usr/bin/env python3
"""Добавляет новые модели из LM Studio в opencode.jsonc."""

import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
LMSTUDIO_URL = "http://localhost:1234/v1/models"
PROVIDER = "lmstudio-nb"


def strip_trailing_commas(text: str) -> str:
    """Убирает завершающие запятые в JSONC для совместимости с json.loads."""
    # Запятая перед ] или }
    return re.sub(r",(\s*[\]\}])", r"\1", text)


def add_trailing_commas(text: str) -> str:
    """Добавляет завершающие запятые обратно в JSON (опционально, для сохранения формата)."""
    # Не добавляем — opencode принимает и обычный JSON
    return text


def main() -> None:
    if not CONFIG.exists():
        print(f"Ошибка: конфиг не найден: {CONFIG}")
        sys.exit(1)

    # Читаем конфиг
    raw = CONFIG.read_text()
    cleaned = strip_trailing_commas(raw)
    config = json.loads(cleaned)

    # Получаем модели с LM Studio
    result = subprocess.run(
        ["curl", "-s", LMSTUDIO_URL],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Ошибка: не удалось получить модели с {LMSTUDIO_URL}")
        sys.exit(1)

    models_data = json.loads(result.stdout)
    new_ids = [m["id"] for m in models_data.get("data", [])]

    # Текущие модели провайдера
    existing_ids = set(config.get("provider", {}).get(PROVIDER, {}).get("models", {}).keys())

    # Находим новые модели
    added = 0
    for model_id in new_ids:
        # Пропускаем embedding модели
        if model_id.startswith("text-embedding"):
            continue

        if model_id not in existing_ids:
            config.setdefault("provider", {}).setdefault(PROVIDER, {}).setdefault("models", {})[model_id] = {
                "name": model_id,
            }
            print(f"Добавлена: {model_id}")
            added += 1

    if added == 0:
        print("Новых моделей не найдено")
    else:
        print(f"Добавлено моделей: {added}")

    # Сохраняем конфиг
    CONFIG.write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    main()
