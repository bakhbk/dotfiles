#!/usr/bin/env python3
# Запуск: uv run ~/dotfiles/scripts/sync-models.py
"""Синхронизирует модели из провайдеров в pi models.json, kilo.jsonc, opencode.jsonc, Zed settings.json и VS Code chatLanguageModels.

Читает провайдеры из ~/.config/dispatch/providers.conf (тот же источник правды, что и copilot.sh),
использует ~/.config/dispatch/model-capabilities.yaml для сведений о возможностях моделей,
fetchит модели через OpenAI-compatible endpoint для каждого провайдера,
и синхронизирует в pi models.json, kilo.jsonc, opencode.jsonc, Zed settings.json и VS Code chatLanguageModels.
"""

import configparser
import hashlib
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

# VS Code chatLanguageModels (несколько возможных путей)
CODE_USER_FOLDER = Path.home() / "Library" / "Application Support" / "Code" / "User"
CODE_USER_LINUX_FOLDER = Path.home() / ".config" / "Code" / "User"
CODE_CHAT_MODELS = CODE_USER_FOLDER / "chatLanguageModels.json"


def _find_chat_models_path() -> Path:
    """Находит путь к chatLanguageModels.json, проверяя macOS и Linux пути."""
    if CODE_CHAT_MODELS.exists():
        return CODE_CHAT_MODELS
    linux_path = CODE_USER_LINUX_FOLDER / "chatLanguageModels.json"
    if linux_path.exists():
        return linux_path
    # Создаём macOS-путь по умолчанию (создаст директорию при записи)
    CODE_USER_FOLDER.mkdir(parents=True, exist_ok=True)
    return CODE_CHAT_MODELS

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
    "max_completion_tokens": 200000,
    "supports_tool_calls": True,
    "supports_images": True
}

# Дефолтные значения для apiKey в pi models.json
PI_API_KEY_DEFAULTS = {
    "lmstudio": "lm-studio",
}

# Timeout для HTTP-запросов (сек)
REQUEST_TIMEOUT = 10

# Путь к таблице capabilities
MODEL_CAPABILITIES_YAML = Path.home() / ".config" / "dispatch" / "model-capabilities.yaml"

# Дефолтные capabilities для моделей, которых нет в таблице
CAPABILITIES_DEFAULTS = {
    "vision": True,
    "tools": True,  # большинство моделей поддерживают инструменты
    "web": True,
}


def _is_reasoning_model(model_id: str) -> bool:
    """Определяет, поддерживает ли модель extended thinking по имени."""
    name = model_id.lower()
    return "reasoning" in name or "thinking" in name


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


def parse_capabilities_yaml(path: Path) -> dict:
    """Парсит model-capabilities.yaml и возвращает {model_id: {vision, tools, web}}."""
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    capabilities = {}
    current_model = None
    current_indent = None
    in_models = False

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not in_models:
            if stripped == "models:":
                in_models = True
            continue

        model_match = re.match(r"^(\s+)([^:\s][^:]*):\s*$", line)
        if model_match:
            current_indent = len(model_match.group(1))
            current_model = model_match.group(2).strip()
            capabilities[current_model] = {}
            continue

        field_match = re.match(r"^(\s+)([^:\s][^:]*):\s*(.+)$", line)
        if field_match and current_model is not None:
            indent = len(field_match.group(1))
            if indent <= current_indent:
                current_model = None
                continue
            key = field_match.group(2).strip()
            value = field_match.group(3).strip().lower()
            if value in {"true", "yes", "y", "1"}:
                capabilities[current_model][key] = True
            elif value in {"false", "no", "n", "0"}:
                capabilities[current_model][key] = False
            else:
                capabilities[current_model][key] = value

    return capabilities


def zed_model_capabilities(caps: dict) -> dict:
    return {
        "tools": caps.get("tools", True),
        "images": caps.get("vision", True),
        "parallel_tool_calls": caps.get("tools", True),
        "prompt_cache_key": caps.get("tools", True),
        "chat_completions": True,
        "interleaved_reasoning": False,
    }


def apply_capabilities(model: dict, caps: dict) -> None:
    """Применяет capabilities из таблицы к модели (overrides defaults)."""
    if not caps:
        return

    model["supports_tool_calls"] = caps.get("tools", True)
    model["supports_images"] = caps.get("vision", True)
    model["capabilities"] = zed_model_capabilities(caps)


def write_json(path: Path, data: dict) -> None:
    """Безопасно и атомарно записывает JSON в файл в кодировке UTF-8."""
    tmp_path = path.with_suffix('.tmp')
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e


def _detect_provider_type(url: str) -> str:
    """Определяет тип провайдера по URL.

    Возвращает:
      - 'lmstudio' — если URL указывает на LM Studio (содержит /api/v1/)
      - 'openai_compatible' — для всех остальных (llama.cpp, Ollama и т.д.)
    """
    lower = url.lower()
    if "/api/v1/" in lower:
        return "lmstudio"
    return "openai_compatible"


def _models_url(provider_type: str, base_url: str) -> tuple[str, bool]:
    """Возвращает URL endpoint для получения списка моделей.

    Для LM Studio: базовый /v1/models + расширенный /api/v1/models.
    Для остальных: только /v1/models.

    Returns:
        (openai_url, needs_extended) — стандартный URL и флаг, нужен ли расширенный API.
    """
    base_url = base_url.rstrip("/")

    if provider_type == "lmstudio":
        return f"{base_url}/v1/models", True
    else:
        return f"{base_url}/models", False


def _normalize_lmstudio_key(key: str) -> str:
    """Нормализует LM Studio key для сопоставления с /v1/models ID.

    Удаляет квантование суффиксы (_Q6_K, @q4_0) и file extensions (.gguf).
    Пример: 'google/gemma-4-12b-qat' → 'gemma-4-12b-qat'
             'qwen/qwen3.6-35b-a3b' → 'qwen3.6-35b-a3b'
    """
    # Убираем publisher prefix (google/, qwen/, etc.)
    normalized = key.split("/", 1)[-1] if "/" in key else key
    return normalized.lower()


def _normalize_v1_model_id(model_id: str) -> str:
    """Нормализует /v1/models ID для сопоставления с LM Studio key.

    Удаляет file extensions и quantization suffixes.
    Пример: 'qwen3.6-35b-a3b_Q6_K' → 'qwen3.6-35b-a3b'
             'Qwen3.6-27B-MTP' → 'qwen3.6-27b-mtp'
             'qwopus3.6-27b-v2-mlx' → 'qwopus3.6-27b-v2-mlx'
    """
    normalized = model_id.lower()

    # Убираем file extensions (case-insensitive match on the end)
    import re
    for ext in [".gguf", ".bin", ".mlx"]:
        if normalized.endswith(ext):
            normalized = normalized[: -len(ext)]

    # Убираем quantization suffixes (_Q6_K, _8bit, etc.)
    normalized = re.sub(r"_[A-Za-z0-9_]+$", "", normalized)

    return normalized


def _parse_lmstudio_details(response_data: dict) -> tuple[dict, dict]:
    """Парсит расширенный LM Studio API response.

    Returns:
        (key_to_details, normalized_id_to_key) где:
          key_to_details = {canonical_key: properties} — по полному ключу
          normalized_id_to_key = {normalized_v1_id: canonical_key} — для сопоставления с /v1/models
          Также строится reverse_map: {base_name_of_key: canonical_key} для fallback-маппинга
          когда v1 ID не имеет publisher prefix (например qwen3.6-35b-a3b_Q6_K → qwen/qwen3.6-35b-a3b)
    """
    result: dict = {}
    normalized_map: dict[str, str] = {}  # norm_v1_id -> canonical_key
    reverse_map: dict[str, str] = {}  # base_name_of_canonical_key -> canonical_key
    all_keys: list[str] = []  # все ключи из extended API

    models_list = response_data.get("models", [])
    for m in models_list:
        key = m.get("key")
        if not key:
            continue

        caps = m.get("capabilities", {})
        quantization = m.get("quantization", {})

        rd = {
            "vision": caps.get("vision"),
            "tools": caps.get("trained_for_tool_use",
caps.get("tool_use")),
            "architecture": m.get("architecture", ""),
            "quantization": quantization.get("name") if isinstance(quantization, dict) else str(quantization),
            "size_bytes": m.get("size_bytes"),
            "max_context_length": m.get("max_context_length"),
        }

        result[key] = rd
        all_keys.append(key)
        # Строим прямой маппинг: нормализованный v1 ID → canonical key
        norm_v1 = _normalize_v1_model_id(key)
        normalized_map[norm_v1] = key
        # Строим reverse-маппинг: basename canonical ключа → key (для fallback)
        base_name = _normalize_v1_model_id(key.split("/", 1)[-1])
        if base_name not in normalized_map or "/" not in key:
            reverse_map[base_name] = key

    return result, normalized_map, reverse_map


def fetch_models(url: str, api_key: str = "") -> tuple[list[str], dict]:
    """Fetch модели с провайдера. Возвращает (model_ids, raw_details).

    model_ids: список ID моделей (базовый endpoint /v1/models)
    raw_details: словарь {model_key: properties} из расширенного API (LM Studio only)

    Для LM Studio зовёт и /v1/models, и /api/v1/models.
    Для остальных (llama.cpp) — только /v1/models, raw_details = {}."""
    base_url = url.rstrip("/")
    provider_type = _detect_provider_type(url)

    # Базовый endpoint для всех провайдеров — получаем model IDs
    openai_url, _ = _models_url(provider_type, base_url)

    # Fetch model IDs from standard OpenAI-compatible endpoint
    req = urllib.request.Request(openai_url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept-Charset", "utf-8")

    model_ids = []
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw_data = resp.read().decode('utf-8', errors='ignore')
            data = json.loads(raw_data)
        model_ids = [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  warn: не удалось получить модели с {openai_url}: {e}")

    # Для LM Studio дополнительно зовём extended API для метаданных
    raw_details: dict = {}
    normalized_map: dict[str, str] = {}  # нормализованный ID → canonical key
    reverse_map: dict[str, str] = {}  # fallback: basename из LM Studio key → canonical_key

    # LM Studio extended API: заменяем /v1 на /api/v1
    api_base = base_url.replace("/v1", "/api/v1").rstrip("/")
    extended_url = f"{api_base}/models"
    try:
        ext_req = urllib.request.Request(extended_url)
        if api_key:
            ext_req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(ext_req, timeout=REQUEST_TIMEOUT) as resp:
            ext_raw = resp.read().decode('utf-8', errors='ignore')
            ext_data = json.loads(ext_raw)
        raw_details, normalized_map, reverse_map = _parse_lmstudio_details(ext_data)
    except Exception as e:
        print(f"  warn: не удалось получить расширенные данные с {extended_url}: {e}")
    else:
        if raw_details and normalized_map:
            print(f"  [lmstudio] получено {len(raw_details)} моделей с расширенными свойствами")
            print(f"  [lmstudio] маппинг {len(normalized_map)} ID из /v1→key")

    return model_ids, raw_details, normalized_map, reverse_map


def sync_to_pi(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict = None, raw_details: dict = None, normalized_map: dict = None, reverse_map: dict = None) -> tuple[int, int, int]:
    """Синхронизирует модели в pi models.json."""
    if PI_MODELS.exists():
        models = read_jsonc(PI_MODELS)
    else:
        models = {"providers": {}}

    providers = models.setdefault("providers", {})

    expected_key = provider_cfg.get("key") or PI_API_KEY_DEFAULTS.get(provider_name, "")
    provider = providers.setdefault(provider_name, {
        "baseUrl": provider_cfg["url"],
        "api": "openai-completions",
        "apiKey": expected_key,
        "models": [],
    })
    provider.setdefault("models", [])

    if provider.get("baseUrl") != provider_cfg["url"]:
        provider["baseUrl"] = provider_cfg["url"]

    if provider.get("apiKey") != expected_key:
        provider["apiKey"] = expected_key

    # LM Studio / локальные серверы не поддерживают reasoning_effort и используют qwen-format
    if provider_name in ("lmstudio",):
        provider.setdefault("compat", {})
        provider["compat"]["supportsReasoningEffort"] = True
        provider["compat"]["thinkingFormat"] = "qwen-chat-template"
    elif capabilities is None:
        capabilities = {}
    if raw_details is None:
        raw_details = {}
    if normalized_map is None:
        normalized_map = {}
    if reverse_map is None:
        reverse_map = {}

    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        # Override YAML capabilities с LM Studio extended API данных
        provider_type = _detect_provider_type(provider_cfg["url"])
        rd = None
        if provider_type == "lmstudio":
            # LM Studio: нормализуем ID и маппим на canonical key
            norm_id = _normalize_v1_model_id(model_id)
            canonical_key = normalized_map.get(norm_id)
            if canonical_key and canonical_key in raw_details:
                rd = raw_details[canonical_key]
            # Fallback: reverse-map по basename (для моделей без publisher prefix в /v1/models)
            if not rd and reverse_map:
                base_name = norm_id  # уже нормализован, без publisher prefix
                for key in reverse_map:
                    if base_name.endswith(key) or (key and norm_id.split('/', 1)[-1] == key):
                        rd = raw_details.get(reverse_map[key])
                        break
        else:
            # llama.cpp: прямой lookup по model_id (meta.n_ctx и т.д.)
            rd = raw_details.get(model_id)
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])
        input_types = ["text"]
        if caps.get("vision"):
            input_types.append("image")

        existing = next((m for m in provider.get("models", []) if m["id"] == model_id), None)
        if existing:
            needs_update = False
            want_reasoning = _is_reasoning_model(model_id)
            if existing.get("reasoning") != want_reasoning:
                existing["reasoning"] = want_reasoning
                needs_update = True
            if set(existing.get("input", [])) != set(input_types):
                existing["input"] = input_types
                needs_update = True

            if needs_update:
                print(f"  pi ({provider_name}): ~{model_id}")
                updated += 1
        else:
            provider["models"].append({
                "id": model_id,
                "reasoning": _is_reasoning_model(model_id),
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


def sync_to_kilo(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict = None, raw_details: dict = None, normalized_map: dict = None, reverse_map: dict = None) -> tuple[int, int, int]:
    """Синхронизирует модели в kilo.jsonc."""
    if not KILO_CONFIG.exists():
        return 0, 0, 0

    config = read_jsonc(KILO_CONFIG)
    provider_key = KILO_PROVIDER_MAP.get(provider_name, provider_name)

    if capabilities is None:
        capabilities = {}
    if raw_details is None:
        raw_details = {}
    config.setdefault("provider", {})
    if normalized_map is None:
        normalized_map = {}
    if reverse_map is None:
        reverse_map = {}

    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": provider_cfg["url"]},
        "models": {},
    })
    provider.setdefault("models", {})

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
        # Override YAML с LM Studio extended API данных
        provider_type = _detect_provider_type(provider_cfg["url"])
        rd = None
        if provider_type == "lmstudio":
            norm_id = _normalize_v1_model_id(model_id)
            canonical_key = normalized_map.get(norm_id)
            if canonical_key and canonical_key in raw_details:
                rd = raw_details[canonical_key]
            # Fallback: reverse-map по basename (для моделей без publisher prefix в /v1/models)
            if not rd and reverse_map:
                base_name = norm_id  # уже нормализован, без publisher prefix
                for key in reverse_map:
                    if base_name.endswith(key) or (key and norm_id.split('/', 1)[-1] == key):
                        rd = raw_details.get(reverse_map[key])
                        break
        else:
            rd = raw_details.get(model_id)
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])

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


def sync_to_opencode(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict = None, raw_details: dict = None, normalized_map: dict = None, reverse_map: dict = None) -> tuple[int, int]:
    """Синхронизирует модели в opencode.jsonc (если файл существует)."""
    if not OPENCODE_CONFIG.exists():
        return 0, 0

    config = read_jsonc(OPENCODE_CONFIG)
    provider_key = provider_name

    if capabilities is None:
        capabilities = {}
    if raw_details is None:
        raw_details = {}
    config.setdefault("provider", {})
    if normalized_map is None:
        normalized_map = {}
    if reverse_map is None:
        reverse_map = {}

    provider = config["provider"].setdefault(provider_key, {
        "name": provider_key.capitalize(),
        "api": "openai-completions",
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": provider_cfg["url"]},
        "models": {},
    })
    provider.setdefault("models", {})

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
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        # Override YAML с LM Studio extended API данных
        provider_type = _detect_provider_type(provider_cfg["url"])
        rd = None
        if provider_type == "lmstudio":
            norm_id = _normalize_v1_model_id(model_id)
            canonical_key = normalized_map.get(norm_id)
            if canonical_key and canonical_key in raw_details:
                rd = raw_details[canonical_key]
            # Fallback: reverse-map по basename (для моделей без publisher prefix в /v1/models)
            if not rd and reverse_map:
                base_name = norm_id  # уже нормализован, без publisher prefix
                for key in reverse_map:
                    if base_name.endswith(key) or (key and norm_id.split('/', 1)[-1] == key):
                        rd = raw_details.get(reverse_map[key])
                        break
        else:
            rd = raw_details.get(model_id)
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])
        modalities = {
            "input": ["image", "text"] if caps.get("vision") else ["text"],
            "output": ["text"],
        }

        existing = provider["models"].get(model_id)
        if existing:
            needs_update = False
            if existing.get("name") != model_id:
                existing["name"] = model_id
                needs_update = True
            if existing.get("modalities") != modalities:
                existing["modalities"] = modalities
                needs_update = True
            if needs_update:
                print(f"  opencode ({provider_key}): ~{model_id}")
                updated += 1
        else:
            provider["models"][model_id] = {
                "name": model_id,
                "modalities": modalities,
            }
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


def sync_to_zed(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict = None, raw_details: dict = None, normalized_map: dict = None, reverse_map: dict = None) -> tuple[int, int, int]:
    """Синхронизирует модели в Zed settings.json."""
    if not ZED_SETTINGS.exists():
        return 0, 0, 0

    config = read_jsonc(ZED_SETTINGS)
    language_models = config.setdefault("language_models", {})

    if capabilities is None:
        capabilities = {}
    if raw_details is None:
        raw_details = {}

    if normalized_map is None:
        normalized_map = {}
    if reverse_map is None:
        reverse_map = {}
    if provider_name in ZED_PROVIDER_MAP:
        target = language_models.setdefault(ZED_PROVIDER_MAP[provider_name], {})
    else:
        target = language_models.setdefault("openai_compatible", {})

    zed_url = normalize_zed_api_url(provider_cfg["url"])

    if provider_name not in ZED_PROVIDER_MAP:
        sub_provider = target.setdefault(provider_name, {
            "api_url": zed_url,
            "available_models": [],
        })
    else:
        sub_provider = target

    if sub_provider.get("api_url") != zed_url:
        sub_provider["api_url"] = zed_url

    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0
    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue
        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        # Override YAML с LM Studio extended API данных
        provider_type = _detect_provider_type(provider_cfg["url"])
        rd = None
        if provider_type == "lmstudio":
            norm_id = _normalize_v1_model_id(model_id)
            canonical_key = normalized_map.get(norm_id)
            if canonical_key and canonical_key in raw_details:
                rd = raw_details[canonical_key]
            # Fallback: reverse-map по basename (для моделей без publisher prefix в /v1/models)
            if not rd and reverse_map:
                base_name = norm_id  # уже нормализован, без publisher prefix
                for key in reverse_map:
                    if base_name.endswith(key) or (key and norm_id.split('/', 1)[-1] == key):
                        rd = raw_details.get(reverse_map[key])
                        break
        else:
            rd = raw_details.get(model_id)
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])

        existing = next((m for m in sub_provider.get("available_models", []) if m.get("name") == model_id), None)
        if existing:
            needs_update = False
            if existing.get("supports_tool_calls") != caps["tools"]:
                existing["supports_tool_calls"] = caps["tools"]
                needs_update = True
            if existing.get("supports_images") != caps["vision"]:
                existing["supports_images"] = caps["vision"]
                needs_update = True
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


def sync_to_code(provider_name: str, provider_cfg: dict, model_ids: list[str], capabilities: dict = None, raw_details: dict = None, normalized_map: dict = None, reverse_map: dict = None) -> tuple[int, int, int]:
    """Синхронизирует модели в VS Code chatLanguageModels.json."""
    models_path = _find_chat_models_path()

    if capabilities is None:
        capabilities = {}
    if raw_details is None:
        raw_details = {}

    if normalized_map is None:
        normalized_map = {}
    if reverse_map is None:
        reverse_map = {}
    if models_path.exists():
        raw = models_path.read_text(encoding="utf-8")
        cleaned = strip_jsonc_comments(raw)

        if not cleaned.strip():
            data: list = []
        else:
            data = json.loads(cleaned)
    else:
        models_path.parent.mkdir(parents=True, exist_ok=True)
        data = []

    # Находим нужный провайдер в массиве
    target = None
    for p in data:
        if isinstance(p, dict) and (p.get("name") == provider_name or p.get("vendor") == "customendpoint"):
            target = p
            break

    # Если не нашли, создаём новый
    if not target:
        target = {
            "name": provider_name,
            "vendor": "customendpoint",
            "apiType": "messages",
            "models": [],
        }
        api_key = provider_cfg.get("key")
        if not api_key:
            # Генерируем placeholder для input secret
            target["apiKey"] = f"$input:chat.lm.secret.-{hashlib.md5(provider_name.encode()).hexdigest()[:8]}"
        else:
            target["apiKey"] = f"$input:chat.lm.secret.-{hashlib.md5(api_key.encode()).hexdigest()[:8]}"
        data.append(target)

    # Обновляем URL если нужно (через models[].url)
    active_ids = {m for m in model_ids if not m.startswith("text-embedding")}

    added = 0
    updated = 0

    for model_id in model_ids:
        if model_id.startswith("text-embedding"):
            continue

        caps = capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        # Override YAML с LM Studio extended API данных
        provider_type = _detect_provider_type(provider_cfg["url"])
        rd = None
        if provider_type == "lmstudio":
            norm_id = _normalize_v1_model_id(model_id)
            canonical_key = normalized_map.get(norm_id)
            if canonical_key and canonical_key in raw_details:
                rd = raw_details[canonical_key]
            # Fallback: reverse-map по basename (для моделей без publisher prefix в /v1/models)
            if not rd and reverse_map:
                base_name = norm_id  # уже нормализован, без publisher prefix
                for key in reverse_map:
                    if base_name.endswith(key) or (key and norm_id.split('/', 1)[-1] == key):
                        rd = raw_details.get(reverse_map[key])
                        break
        else:
            rd = raw_details.get(model_id)
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])

        existing = next((m for m in target.get("models", []) if m.get("id") == model_id), None)
        if existing:
            needs_update = False
            # Обновляем toolCalling и vision из capabilities
            if existing.get("toolCalling") != caps.get("tools", True):
                existing["toolCalling"] = caps.get("tools", True)
                needs_update = True
            if existing.get("vision") != caps.get("vision", True):
                existing["vision"] = caps.get("vision", True)
                needs_update = True

            if needs_update:
                print(f"  code ({provider_name}): ~{model_id}")
                updated += 1
        else:
            model_entry = {
                "id": model_id,
                "name": model_id,  # как в конфиге на скриншоте: "qwen/qwen3.6-35b-a3b"
                "url": provider_cfg["url"],  # базовый URL провайдера не хранится на уровне модели
                "toolCalling": caps.get("tools", True),
                "vision": caps.get("vision", True),
            }

            # Добавляем разумные дефолты для max токенов
            model_entry["maxInputTokens"] = 128000
            model_entry["maxOutputTokens"] = 16000

            target.setdefault("models", []).append(model_entry)
            print(f"  code ({provider_name}): +{model_id}")
            added += 1

    # Удаляем устаревшие модели
    removed = 0
    for model in list(target.get("models", [])):
        if model.get("id") not in active_ids:
            target["models"].remove(model)
            print(f"  code ({provider_name}): -{model.get('id')}")
            removed += 1

    # Записываем обратно
    write_json(models_path, data)

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


def normalize_zed_api_url(url: str) -> str:
    url = url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/api/v0"


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

    # Парсим YAML capabilities
    if MODEL_CAPABILITIES_YAML.exists():
        capabilities = parse_capabilities_yaml(MODEL_CAPABILITIES_YAML)
        print(f"Загружено {len(capabilities)} моделей из YAML capabilities")
    else:
        capabilities = {}
        print(f"Не найден {MODEL_CAPABILITIES_YAML}, capabilities не загружены")

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
        model_ids, raw_details, normalized_map, reverse_map = fetch_models(provider_cfg["url"], provider_cfg.get("key", ""))

        if not model_ids:
            print(f"  Нет моделей для {provider_name}")
            continue

        added_pi, updated_pi, removed_pi = sync_to_pi(provider_name, provider_cfg, model_ids, capabilities, raw_details, normalized_map, reverse_map)
        added_kilo, updated_kilo, removed_kilo = sync_to_kilo(provider_name, provider_cfg, model_ids, capabilities, raw_details, normalized_map, reverse_map)
        added_opencode, removed_opencode = sync_to_opencode(provider_name, provider_cfg, model_ids, capabilities, raw_details, normalized_map, reverse_map)
        added_zed, updated_zed, removed_zed = sync_to_zed(provider_name, provider_cfg, model_ids, capabilities, raw_details, normalized_map, reverse_map)
        added_code, updated_code, removed_code = sync_to_code(provider_name, provider_cfg, model_ids, capabilities, raw_details, normalized_map, reverse_map)

        total_added += added_pi + added_kilo + added_opencode + added_zed + added_code
        total_updated += updated_pi + updated_kilo + updated_zed + updated_code
        total_removed += removed_pi + removed_kilo + removed_opencode + removed_zed + removed_code

    print(f"\nИтого: добавлено {total_added}, обновлено {total_updated}, удалено {total_removed} моделей")


if __name__ == "__main__":
    main()
