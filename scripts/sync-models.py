#!/usr/bin/env python3
"""Синхронизирует модели из провайдеров в pi models.json, kilo.jsonc, opencode.jsonc и Zed settings.json.

Читает провайдеры из ~/.config/dispatch/providers.conf (тот же источник правды, что и copilot.sh),
fetchит модели через OpenAI-compatible endpoint для каждого провайдера,
и синхронизирует в pi models.json, kilo.jsonc, opencode.jsonc и Zed settings.json.
"""

import configparser
import json
import re
import sys
import urllib.request
from pathlib import Path

# Пути к конфигам
PROVIDERS_CONF = Path.home() / ".config" / "dispatch" / "providers.conf"
PI_MODELS = Path.home() / ".pi" / "agent" / "models.json"
KILO_CONFIG = Path.home() / ".config" / "kilo" / "kilo.jsonc"
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
ZED_SETTINGS = Path.home() / ".config" / "zed" / "settings.json"

# Маппинг имён провайдеров из providers.conf → kilo
KILO_PROVIDER_MAP = {
    "lmstudio": "nb",
    "kr-jarvis": "kr",
}

# Маппинг имён провайдеров из providers.conf → Zed language_models keys
ZED_PROVIDER_MAP = {
    "lmstudio": "lmstudio",
}
# Все остальные провайдеры попадают под openai_compatible

# Дефолтные параметры модели для Zed
ZED_MODEL_DEFAULTS = {
    "supports_tool_calls": True,
    "supports_images": False,
    "max_tokens": 200000,
    "max_completion_tokens": 200000,
    "capabilities": {
        "tools": True,
        "images": False,
        "parallel_tool_calls": True,
        "prompt_cache_key": True,
        "chat_completions": True,
        "interleaved_reasoning": False,
    },
}

# Дефолтные значения для apiKey в pi models.json
PI_API_KEY_DEFAULTS = {
    "lmstudio": "lm-studio",
}

# Timeout для HTTP-запросов (сек)
REQUEST_TIMEOUT = 10

# Путь к таблице capabilities
MODEL_CAPABILITIES_FILE = Path.home() / ".config" / "dispatch" / "model-capabilities.md"

# Дефолтные capabilities для моделей, которых нет в таблице
CAPABILITIES_DEFAULTS = {
    "vision": False,
    "tools": True,  # большинство моделей поддерживают инструменты
    "web": False,
}


def strip_trailing_commas(text: str) -> str:
    """Убирает завершающие запятые в JSONC для совместимости с json.loads."""
    return re.sub(r",(\s*[\]\}])", r"\1", text)


def strip_jsonc_comments(text: str) -> str:
    """Убирает комментарии // из JSONC, сохраняя строки с // внутри."""
    lines = text.split("\n")
    result = []
    for line in lines:
        # Ищем // вне строк (простой подход: считаем, что строки не содержат \" внутри)
        in_string = False
        escaped = False
        comment_start = -1
        for i, ch in enumerate(line):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/" and not in_string:
                comment_start = i
                break
        if comment_start >= 0:
            line = line[:comment_start]
        result.append(line)
    return "\n".join(result)


def read_jsonc(path: Path) -> dict:
    """Читает JSONC-файл, возвращая распарсенный dict."""
    raw = path.read_text()
    cleaned = strip_jsonc_comments(raw)
    cleaned = strip_trailing_commas(cleaned)
    return json.loads(cleaned)


def parse_capabilities_table(path: Path) -> dict:
    """Парсит model-capabilities.md и возвращает {model_id: {vision, tools, web}}."""
    if not path.exists():
        return {}

    raw = path.read_text()
    lines = raw.split("\n")

    # Находим строку с заголовком таблицы
    table_start = -1
    for i, line in enumerate(lines):
        if "| Название модели" in line:
            table_start = i
            break

    if table_start < 0:
        return {}

    capabilities = {}
    for line in lines[table_start + 2:]:  # пропускаем заголовок и разделитель
        line = line.strip()
        if not line or not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 4:
            model_id = parts[0]
            vision = "✅" in parts[1]
            tools = "✅" in parts[2]
            web = "✅" in parts[3]
            capabilities[model_id] = {
                "vision": vision,
                "tools": tools,
                "web": web,
            }

    return capabilities


def apply_capabilities(model: dict, caps: dict) -> None:
    """Применяет capabilities из таблицы к модели (overrides defaults)."""
    if not caps:
        return

    # Zed: supports_tool_calls, supports_images
    model["supports_tool_calls"] = caps.get("tools", True)
    model["supports_images"] = caps.get("vision", False)

    # Zed capabilities sub-object
    if "capabilities" in model:
        model["capabilities"]["tools"] = caps.get("tools", True)
        model["capabilities"]["images"] = caps.get("vision", False)


def write_json(path: Path, data: dict) -> None:
    """Записывает JSON в файл."""
    path.write_text(json.dumps(data, indent=2) + "\n")


def fetch_models(url: str, api_key: str = "") -> list[str]:
    """Fetch модели с OpenAI-compatible endpoint. Возвращает список model IDs."""
    req = urllib.request.Request(f"{url}/models")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  warn: не удалось получить модели с {url}: {e}")
        return []


def sync_to_pi(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int]:
    """Синхронизирует модели в pi models.json."""
    if not PI_MODELS.exists():
        print(f"pi models.json не найден: {PI_MODELS}")
        return 0, 0

    models = read_jsonc(PI_MODELS)
    providers = models.setdefault("providers", {})

    # Создаём/получаем секцию провайдера
    provider = providers.setdefault(provider_name, {
        "baseUrl": provider_cfg["url"],
        "api": "openai-completions",
        "apiKey": provider_cfg.get("key") or PI_API_KEY_DEFAULTS.get(provider_name, ""),
        "models": [],
    })

    # Обновляем baseUrl если изменился
    if provider.get("baseUrl") != provider_cfg["url"]:
        provider["baseUrl"] = provider_cfg["url"]

    # Обновляем apiKey если изменился
    expected_key = provider_cfg.get("key") or PI_API_KEY_DEFAULTS.get(provider_name, "")
    if provider.get("apiKey") != expected_key:
        provider["apiKey"] = expected_key

    existing_ids = {m["id"] for m in provider.get("models", [])}
    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        input_types = ["text"]
        if caps.get("vision"):
            input_types.append("image")

        existing = next((m for m in provider.get("models", []) if m["id"] == model_id), None)
        if existing:
            # Обновляем input если изменились capabilities
            needs_update = False
            if set(existing.get("input", [])) != set(input_types):
                existing["input"] = input_types
                needs_update = True
            if needs_update:
                print(f"  pi ({provider_name}): ~{model_id}")
                updated += 1
        else:
            provider["models"].append({
                "id": model_id,
                "toolCalling": True,
                "input": input_types,
            })
            print(f"  pi ({provider_name}): +{model_id}")
            added += 1

    removed = 0
    for model in list(provider["models"]):
        if model["id"] not in active_ids:
            provider["models"].remove(model)
            print(f"  pi ({provider_name}): -{model['id']}")
            removed += 1

    write_json(PI_MODELS, models)
    return added, updated, removed


def sync_to_kilo(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int]:
    """Синхронизирует модели в kilo.jsonc."""
    if not KILO_CONFIG.exists():
        print(f"kilo.jsonc не найден: {KILO_CONFIG}")
        return 0, 0

    config = read_jsonc(KILO_CONFIG)
    provider_key = KILO_PROVIDER_MAP.get(provider_name, provider_name)
    config.setdefault("provider", {})

    # Создаём/получаем секцию провайдера
    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": provider_cfg["url"]},
        "models": {},
    })

    # Обновляем baseURL если изменился
    if provider.get("options", {}).get("baseURL") != provider_cfg["url"]:
        provider.setdefault("options", {})["baseURL"] = provider_cfg["url"]

    # Обновляем name если это новый провайдер
    if provider_key not in KILO_PROVIDER_MAP:
        provider["name"] = provider_key.capitalize()

    existing_ids = set(provider.get("models", {}).keys())
    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)

        existing = provider["models"].get(model_id)
        if existing:
            # Обновляем reasoning если изменились capabilities
            needs_update = False
            if existing.get("reasoning") != caps.get("tools", True):
                existing["reasoning"] = caps.get("tools", True)
                needs_update = True
            if needs_update:
                print(f"  kilo ({provider_key}): ~{model_id}")
                updated += 1
        else:
            provider["models"][model_id] = {
                "name": model_id,
                "reasoning": caps.get("tools", True),
            }
            print(f"  kilo ({provider_key}): +{model_id}")
            added += 1

    removed = 0
    for model_id in list(existing_ids):
        if model_id not in active_ids:
            del provider["models"][model_id]
            print(f"  kilo ({provider_key}): -{model_id}")
            removed += 1

    write_json(KILO_CONFIG, config)
    return added, updated, removed


def sync_to_opencode(provider_name: str, provider_cfg: dict, model_ids: list[str]) -> tuple[int, int]:
    """Синхронизирует модели в opencode.jsonc (если файл существует)."""
    if not OPENCODE_CONFIG.exists():
        print(f"opencode.jsonc не найден: {OPENCODE_CONFIG}")
        return 0, 0

    config = read_jsonc(OPENCODE_CONFIG)
    provider_key = provider_name  # для opencode используем имя секции как есть
    config.setdefault("provider", {})

    # Создаём/получаем секцию провайдера
    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "models": {},
    })

    existing_ids = set(provider.get("models", {}).keys())
    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        if model_id not in existing_ids:
            provider["models"][model_id] = {"name": model_id}
            print(f"  opencode ({provider_key}): +{model_id}")
            added += 1

    removed = 0
    for model_id in list(existing_ids):
        if model_id not in active_ids:
            del provider["models"][model_id]
            print(f"  opencode ({provider_key}): -{model_id}")
            removed += 1

    write_json(OPENCODE_CONFIG, config)
    return added, removed


def sync_to_zed(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int]:
    """Синхронизирует модели в Zed settings.json.

    Zed использует структуру language_models, где:
    - lmstudio → language_models.lmstudio.available_models
    - другие провайдеры → language_models.openai_compatible.{sub_provider}.available_models
    """
    if not ZED_SETTINGS.exists():
        print(f"zed settings.json не найден: {ZED_SETTINGS}")
        return 0, 0

    config = read_jsonc(ZED_SETTINGS)
    language_models = config.setdefault("language_models", {})

    # Определяем, куда класть модели провайдера
    if provider_name in ZED_PROVIDER_MAP:
        target = language_models[ZED_PROVIDER_MAP[provider_name]]
    else:
        # Для провайдеров без прямого маппинга — под openai_compatible
        target = language_models.setdefault("openai_compatible", {})

    # Если это под-провайдер openai_compatible, создаём/обновляем секцию
    if provider_name not in ZED_PROVIDER_MAP:
        sub_provider = target.setdefault(provider_name, {
            "api_url": provider_cfg["url"],
            "available_models": [],
        })
    else:
        sub_provider = target

    # Обновляем api_url если изменился
    if "api_url" in sub_provider and sub_provider["api_url"] != provider_cfg["url"]:
        sub_provider["api_url"] = provider_cfg["url"]

    existing_names = {m.get("name") for m in sub_provider.get("available_models", [])}
    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)

        # Ищем существующую модель
        existing = next((m for m in sub_provider.get("available_models", []) if m.get("name") == model_id), None)
        if existing:
            # Обновляем capabilities если изменились
            needs_update = False
            if existing.get("supports_tool_calls") != caps["tools"]:
                existing["supports_tool_calls"] = caps["tools"]
                needs_update = True
            if existing.get("supports_images") != caps["vision"]:
                existing["supports_images"] = caps["vision"]
                needs_update = True
            if "capabilities" in existing:
                if existing["capabilities"].get("tools") != caps["tools"]:
                    existing["capabilities"]["tools"] = caps["tools"]
                    needs_update = True
                if existing["capabilities"].get("images") != caps["vision"]:
                    existing["capabilities"]["images"] = caps["vision"]
                    needs_update = True
            if needs_update:
                print(f"  zed ({provider_name}): ~{model_id}")
                updated += 1
        else:
            # Добавляем новую модель
            model_data = {
                **ZED_MODEL_DEFAULTS,
                "name": model_id,
            }
            apply_capabilities(model_data, caps)
            sub_provider.setdefault("available_models", []).append(model_data)
            print(f"  zed ({provider_name}): +{model_id}")
            added += 1

    removed = 0
    for model in list(sub_provider.get("available_models", [])):
        if model.get("name") not in active_ids:
            sub_provider["available_models"].remove(model)
            print(f"  zed ({provider_name}): -{model.get('name')}")
            removed += 1

    write_json(ZED_SETTINGS, config)
    return added, updated, removed


def parse_providers_conf() -> dict:
    """Парсит providers.conf и возвращает словарь {имя_провайдера: config_dict}."""
    if not PROVIDERS_CONF.exists():
        print(f"providers.conf не найден: {PROVIDERS_CONF}")
        return {}

    config = configparser.ConfigParser()
    config.read(PROVIDERS_CONF)

    providers = {}
    for section in config.sections():
        providers[section] = {
            "url": config.get(section, "url", fallback=""),
            "key": config.get(section, "key", fallback=""),
        }

    return providers


def main() -> None:
    print(f"Читаю провайдеры из {PROVIDERS_CONF}")

    # Парсим таблицу capabilities
    capabilities = parse_capabilities_table(MODEL_CAPABILITIES_FILE)
    if capabilities:
        print(f"Загружено {len(capabilities)} моделей из таблицы capabilities")

    providers = parse_providers_conf()

    if not providers:
        print("Нет провайдеров для синхронизации")
        return

    total_added = 0
    total_removed = 0

    for provider_name, provider_cfg in providers.items():
        print(f"\nОбработка провайдера: {provider_name} ({provider_cfg['url']})")
        model_ids = fetch_models(provider_cfg["url"], provider_cfg.get("key", ""))

        if not model_ids:
            print(f"  Нет моделей для {provider_name}")
            continue

        added_pi, updated_pi, removed_pi = sync_to_pi(provider_name, provider_cfg, model_ids, capabilities)
        added_kilo, updated_kilo, removed_kilo = sync_to_kilo(provider_name, provider_cfg, model_ids, capabilities)
        added_opencode, removed_opencode = sync_to_opencode(provider_name, provider_cfg, model_ids)
        added_zed, updated_zed, removed_zed = sync_to_zed(provider_name, provider_cfg, model_ids, capabilities)

        total_added += added_pi + added_kilo + added_opencode + added_zed
        total_updated = updated_pi + updated_kilo + updated_zed
        total_removed += removed_pi + removed_kilo + removed_opencode + removed_zed

    print(f"\nИтого: добавлено {total_added}, удалено {total_removed} моделей")


if __name__ == "__main__":
    main()
