#!/usr/bin/env python3
"""Добавляет новые модели из LM Studio в opencode.jsonc, pi models.json и kilo.jsonc."""

import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
PI_MODELS = Path.home() / ".pi" / "agent" / "models.json"
KILO_CONFIG = Path.home() / ".config" / "kilo" / "kilo.jsonc"
LMSTUDIO_URL = "http://localhost:1234/v1/models"
PROVIDER = "lmstudio-nb"


def strip_trailing_commas(text: str) -> str:
    """Убирает завершающие запятые в JSONC для совместимости с json.loads."""
    # Запятая перед ] или } (включая пробелы/переносы строк между ними)
    return re.sub(r",(\s*[\]\}])", r"\1", text)


def add_trailing_commas(text: str) -> str:
    """Добавляет завершающие запятые обратно в JSON (опционально, для сохранения формата)."""
    # Не добавляем — opencode принимает и обычный JSON
    return text


def add_models_to_opencode(config: dict, new_ids: list[str]) -> tuple[int, int]:
    """Добавляет новые модели и удаляет отсутствующие в opencode.jsonc."""
    provider = config.setdefault("provider", {}).setdefault(PROVIDER, {}).setdefault("models", {})
    existing_ids = set(provider.keys())
    active_ids = {m for m in new_ids if not m.startswith("text-embedding")}

    added = 0
    for model_id in new_ids:
        if model_id.startswith("text-embedding"):
            continue
        if model_id not in existing_ids:
            provider[model_id] = {"name": model_id}
            print(f"  opencode: +{model_id}")
            added += 1

    removed = 0
    for model_id in list(existing_ids):
        if model_id not in active_ids:
            del provider[model_id]
            print(f"  opencode: -{model_id}")
            removed += 1

    return added, removed


def add_models_to_pi(models: dict, new_ids: list[str]) -> tuple[int, int]:
    """Добавляет новые модели и удаляет отсутствующие в pi models.json."""
    providers = models.setdefault("providers", {})
    lmstudio = providers.setdefault("lmstudio", {"baseUrl": "http://localhost:1234/v1", "api": "openai-completions", "apiKey": "lm-studio", "models": []})
    existing_ids = {m["id"] for m in lmstudio.get("models", [])}
    active_ids = {m for m in new_ids if not m.startswith("text-embedding")}

    added = 0
    for model_id in new_ids:
        if model_id.startswith("text-embedding"):
            continue
        if model_id not in existing_ids:
            lmstudio["models"].append({
                "id": model_id,
                "toolCalling": True,
                "input": ["text"],
            })
            print(f"  pi: +{model_id}")
            added += 1

    removed = 0
    for model in list(lmstudio["models"]):
        if model["id"] not in active_ids:
            lmstudio["models"].remove(model)
            print(f"  pi: -{model['id']}")
            removed += 1

    return added, removed


def add_models_to_kilo(config: dict, new_ids: list[str]) -> tuple[int, int]:
    """Добавляет новые модели и удаляет отсутствующие в kilo.jsonc."""
    provider = config.get("provider", {}).get("nb", {})
    models = provider.setdefault("models", {})
    existing_ids = set(models.keys())
    active_ids = {m for m in new_ids if not m.startswith("text-embedding")}

    added = 0
    for model_id in new_ids:
        if model_id.startswith("text-embedding"):
            continue
        if model_id not in existing_ids:
            models[model_id] = {
                "name": model_id,
                "reasoning": True,
            }
            print(f"  kilo: +{model_id}")
            added += 1

    removed = 0
    for model_id in list(existing_ids):
        if model_id not in active_ids:
            del models[model_id]
            print(f"  kilo: -{model_id}")
            removed += 1

    return added, removed


def main() -> None:
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

    total_added = 0
    total_removed = 0

    # opencode.jsonc
    if CONFIG.exists():
        raw = CONFIG.read_text()
        cleaned = strip_trailing_commas(raw)
        config = json.loads(cleaned)
        added, removed = add_models_to_opencode(config, new_ids)
        total_added += added
        total_removed += removed
        if added > 0 or removed > 0:
            CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    else:
        print(f"opencode.jsonc не найден: {CONFIG}")

    # pi models.json
    if PI_MODELS.exists():
        raw = PI_MODELS.read_text()
        cleaned = strip_trailing_commas(raw)
        models = json.loads(cleaned)
        added, removed = add_models_to_pi(models, new_ids)
        total_added += added
        total_removed += removed
        if added > 0 or removed > 0:
            PI_MODELS.write_text(json.dumps(models, indent=2) + "\n")
    else:
        print(f"pi models.json не найден: {PI_MODELS}")

    # kilo.jsonc
    if KILO_CONFIG.exists():
        raw = KILO_CONFIG.read_text()
        cleaned = strip_trailing_commas(raw)
        config = json.loads(cleaned)
        added, removed = add_models_to_kilo(config, new_ids)
        total_added += added
        total_removed += removed
        if added > 0 or removed > 0:
            KILO_CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    else:
        print(f"kilo.jsonc не найден: {KILO_CONFIG}")

    if total_added == 0 and total_removed == 0:
        print("Новых моделей не найдено")
    else:
        parts = [f"Добавлено моделей: {total_added}"]
        if total_removed > 0:
            parts.append(f"Удалено моделей: {total_removed}")
        print("\n".join(parts))


if __name__ == "__main__":
    main()
