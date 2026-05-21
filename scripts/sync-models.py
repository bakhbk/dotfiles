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
import urllib.parse
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
    "display_name": None,  # заполняется из name если не задан
    "max_tokens": 200000,
    "supports_tool_calls": True,
    "supports_images": False,
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
    """Читает JSONC-файл, возвращая распарсенный dict с поддержкой UTF-8."""
    raw = path.read_text(encoding="utf-8")
    cleaned = strip_jsonc_comments(raw)
    cleaned = strip_trailing_commas(cleaned)
    return json.loads(cleaned)


def parse_capabilities_table(path: Path) -> dict:
    """Парсит model-capabilities.md и возвращает {model_id: {vision, tools, web}}."""
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
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
    """Безопасно и атомарно записывает JSON в файл в кодировке UTF-8."""
    tmp_path = path.with_suffix('.tmp')
    try:
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e


def fetch_models(url: str, api_key: str = "") -> list[str]:
    """Fetch модели с OpenAI-compatible endpoint. Возвращает список model IDs."""
    base_url = url.rstrip("/")
    req = urllib.request.Request(f"{base_url}/models")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept-Charset", "utf-8")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw_data = resp.read().decode('utf-8', errors='ignore')
            data = json.loads(raw_data)
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  warn: не удалось получить модели с {url}: {e}")
        return []


def sync_to_pi(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int, int]:
    """Синхронизирует модели в pi models.json."""
    if not PI_MODELS.exists():
        print(f"pi models.json не найден: {PI_MODELS}")
        return 0, 0, 0

    models = read_jsonc(PI_MODELS)
    providers = models.setdefault("providers", {})

    expected_key = provider_cfg.get("key") or PI_API_KEY_DEFAULTS.get(provider_name, "")
    provider = providers.setdefault(provider_name, {
        "baseUrl": provider_cfg["url"],
        "api": "openai-completions",
        "apiKey": expected_key,
        "models": [],
    })

    if provider.get("baseUrl") != provider_cfg["url"]:
        provider["baseUrl"] = provider_cfg["url"]

    if provider.get("apiKey") != expected_key:
        provider["apiKey"] = expected_key

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


def sync_to_kilo(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int, int]:
    """Синхронизирует модели в kilo.jsonc."""
    if not KILO_CONFIG.exists():
        print(f"kilo.jsonc не найден: {KILO_CONFIG}")
        return 0, 0, 0

    config = read_jsonc(KILO_CONFIG)
    provider_key = KILO_PROVIDER_MAP.get(provider_name, provider_name)
    config.setdefault("provider", {})

    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": provider_cfg["url"]},
        "models": {},
    })

    if provider.get("options", {}).get("baseURL") != provider_cfg["url"]:
        provider.setdefault("options", {})["baseURL"] = provider_cfg["url"]

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
    provider_key = provider_name
    config.setdefault("provider", {})

    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "api": "openai-completions",
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": provider_cfg["url"]},
        "models": {},
    })

    if provider.get("name") != provider_key.capitalize():
        provider["name"] = provider_key.capitalize()
    if provider.get("api") != "openai-completions":
        provider["api"] = "openai-completions"
    if provider.get("npm") != "@ai-sdk/openai-compatible":
        provider["npm"] = "@ai-sdk/openai-compatible"
    if provider.get("options", {}).get("baseURL") != provider_cfg["url"]:
        provider.setdefault("options", {})["baseURL"] = provider_cfg["url"]
    if provider_cfg.get("key"):
        provider.setdefault("options", {})["apiKey"] = provider_cfg["key"]
    elif provider.get("options") and "apiKey" in provider["options"]:
        del provider["options"]["apiKey"]

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


def sync_to_zed(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict) -> tuple[int, int, int]:
    """Синхронизирует модели в Zed settings.json."""
    if not ZED_SETTINGS.exists():
        print(f"zed settings.json не найден: {ZED_SETTINGS}")
        return 0, 0, 0

    config = read_jsonc(ZED_SETTINGS)
    language_models = config.setdefault("language_models", {})

    if provider_name in ZED_PROVIDER_MAP:
        target = language_models.setdefault(ZED_PROVIDER_MAP[provider_name], {})
    else:
        target = language_models.setdefault("openai_compatible", {})

    if provider_name not in ZED_PROVIDER_MAP:
        sub_provider = target.setdefault(provider_name, {
            "api_url": provider_cfg["url"],
            "available_models": [],
        })
    else:
        sub_provider = target

    if "api_url" in sub_provider and sub_provider["api_url"] != provider_cfg["url"]:
        sub_provider["api_url"] = provider_cfg["url"]

    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)

        existing = next((m for m in sub_provider.get("available_models", []) if m.get("name") == model_id), None)
        if existing:
            needs_update = False
            if existing.get("supports_tool_calls") != caps["tools"]:
                existing["supports_tool_calls"] = caps["tools"]
                needs_update = True
            if existing.get("supports_images") != caps["vision"]:
                existing["supports_images"] = caps["vision"]
                needs_update = True
            if "capabilities" in existing:
                del existing["capabilities"]
                needs_update = True
            if "max_completion_tokens" in existing:
                del existing["max_completion_tokens"]
                needs_update = True
            if "display_name" not in existing:
                existing["display_name"] = model_id.split("/")[-1]
                needs_update = True
            if needs_update:
                print(f"  zed ({provider_name}): ~{model_id}")
                updated += 1
        else:
            model_data = {
                **ZED_MODEL_DEFAULTS,
                "name": model_id,
                "display_name": model_id.split("/")[-1],
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


def normalize_provider_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url or url.lower() in {"undefined", "null", "none"}:
        return ""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return url


def normalize_api_key(key: str) -> str:
    key = key.strip()
    return "" if key.lower() in {"undefined", "null", "none"} else key


def parse_providers_conf() -> dict:
    """Парсит providers.conf и возвращает словарь {имя_провайдера: config_dict}."""
    if not PROVIDERS_CONF.exists():
        print(f"providers.conf не найден: {PROVIDERS_CONF}")
        return {}

    config = configparser.ConfigParser()
    config.read(PROVIDERS_CONF)

    providers = {}
    for section in config.sections():
        url = normalize_provider_url(config.get(section, "url", fallback=""))
        if not url:
            print(f"  пропуск провайдера {section}: неверный или отсутствующий URL")
            continue
        providers[section] = {
            "url": url,
            "key": normalize_api_key(config.get(section, "key", fallback="")),
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
    total_updated = 0
    total_removed = 0

    for provider_name, provider_cfg in providers.items():
        if not provider_cfg["url"]:
            print(f"\nПропуск провайдера {provider_name}: отсутствует URL")
            continue

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
        total_updated += updated_pi + updated_kilo + updated_zed
        total_removed += removed_pi + removed_kilo + removed_opencode + removed_zed

    print(f"\nИтого: добавлено {total_added}, обновлено {total_updated}, удалено {total_removed} моделей")


if __name__ == "__main__":
    main()
