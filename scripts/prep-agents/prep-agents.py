#!/usr/bin/env python3
# Запуск: uv run ~/dotfiles/scripts/prep-agents.py [--max-context N] [--provider NAME]
"""Подготовка AI-агентов: синхронизация моделей из провайдеров в pi, kilo, opencode, Zed, VS Code.

Читает провайдеры из ~/.config/dispatch/providers.conf,
fetchит модели через OpenAI-compatible endpoint для каждого провайдера,
и синхронизирует во все поддерживаемые инструменты.

Принципы: DRY, KISS, SOLID, YAGNI, data-driven architecture.

📖 Как расширять/изменять: см. README.md — разделы «Архитектура», «Расширение», «Чего не делать».
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import logging
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

# ============================================================================
# Пути к конфигам
# ============================================================================
PROVIDERS_CONF = Path.home() / ".config" / "dispatch" / "providers.conf"
MODEL_CAPABILITIES_YAML = Path.home() / ".config" / "dispatch" / "model-capabilities.yaml"

PI_MODELS = Path.home() / ".pi" / "agent" / "models.json"
KILO_CONFIG = Path.home() / ".config" / "kilo" / "kilo.jsonc"
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
ZED_SETTINGS = Path.home() / ".config" / "zed" / "settings.json"

CODE_USER_FOLDER = Path.home() / "Library" / "Application Support" / "Code" / "User"
CODE_USER_LINUX_FOLDER = Path.home() / ".config" / "Code" / "User"
CODE_CHAT_MODELS = CODE_USER_FOLDER / "chatLanguageModels.json"

# ============================================================================
# Маппинги провайдеров
# ============================================================================
# Маппинг имён провайдеров из providers.conf → целевой ключ в конфиге
# Формат: {"имя_из_providers.conf": "ключ_в_конфиге"}
KILO_PROVIDER_MAP = {
    # "source-provider": "target-key",
}

# Маппинг для Zed: {"имя_из_providers.conf": "ключ_в_language_models"}
ZED_PROVIDER_MAP = {
    # "source-provider": "target-key",
}

# ============================================================================
# Утилиты JSONC
# ============================================================================
def strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[\]\}])", r"\1", text)


def strip_jsonc_comments(text: str) -> str:
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
    raw = path.read_text(encoding="utf-8")
    cleaned = strip_jsonc_comments(raw)
    cleaned = strip_trailing_commas(cleaned)
    return json.loads(cleaned)


def write_json(path: Path, data: Any) -> None:
    tmp_path = path.with_suffix('.tmp')
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e


# ============================================================================
# Абстракции (Protocols)
# ============================================================================
T = TypeVar('T')


class Storage(Protocol[T]):
    """Абстракция чтения/записи конфига."""
    def read(self) -> T: ...
    def write(self, data: T) -> None: ...


class ProviderAccessor(Protocol):
    """Абстракция работы с провайдером внутри конфига."""
    def get_provider(self, config: dict, key: str) -> dict: ...


class ModelBuilder(Protocol):
    """Абстракция создания/обновления модели."""
    def create(self, model_id: str, caps: dict, rd: dict | None, max_context: int | None) -> dict: ...
    def update(self, existing: dict, model_id: str, caps: dict, rd: dict | None, max_context: int | None) -> bool: ...


# ============================================================================
# Schema — сборка syncer'а из компонентов
# ============================================================================
@dataclass
class Schema:
    storage: Storage[dict]
    accessor: ProviderAccessor
    builder: ModelBuilder
    provider_map: dict[str, str] = field(default_factory=dict)
    name: str = ""  # для логирования


# ============================================================================
# Data classes — данные от fetch и контекст синхронизации
# ============================================================================
@dataclass(frozen=True)
class ProviderData:
    """Результат fetch_models — данные от провайдера."""
    model_ids: tuple[str, ...]
    raw_details: dict[str, dict]
    normalized_map: dict[str, str]
    reverse_map: dict[str, str]


@dataclass
class SyncContext:
    """Контекст синхронизации — все данные, нужные sync_provider."""
    provider_name: str
    provider_cfg: dict[str, str]
    capabilities: dict[str, dict]
    max_context: int | None = None


@dataclass
class SyncArgs:
    """Аргументы CLI — легко расширять."""
    max_context: int | None = None
    provider_filter: str | None = None
    cleanup: bool = False  # удалять модели удалённых провайдеров
    verbose: bool = False  # по умолчанию quiet, -v включает логи

    @classmethod
    def from_cli(cls) -> "SyncArgs":
        parser = argparse.ArgumentParser(description="Подготовка AI-агентов к работе")
        parser.add_argument("--max-context", type=int, default=None,
                            help="Принудительный максимум контекста (токены)")
        parser.add_argument("--provider", default=None,
                            help="Синхронизировать только указанного провайдера")
        parser.add_argument("--cleanup", action="store_true",
                            help="Удалить модели провайдеров, которых нет в providers.conf")
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="Показывать все логи (по умолчанию только ошибки)")
        args = parser.parse_args()
        return cls(
            max_context=args.max_context,
            provider_filter=args.provider,
            cleanup=args.cleanup,
            verbose=args.verbose,
        )


# ============================================================================
# Логирование
# ============================================================================
logger = logging.getLogger("prep-agents")


def setup_logging(verbose: bool) -> None:
    logger.setLevel(logging.INFO if verbose else logging.WARNING)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)


# ============================================================================
# Утилиты resolve details и capabilities
# ============================================================================
CAPABILITIES_DEFAULTS = {
    "vision": True,
    "tools": True,
    "web": True,
}


def resolve_model_details(model_id: str, data: ProviderData) -> dict | None:
    """Разрешает детали модели из raw_details через normalized_map.

    Один раз для всех syncer'ов — DRY.
    """
    # Нормализуем ID
    normalized = model_id.lower()
    for ext in [".gguf", ".bin", ".mlx"]:
        if normalized.endswith(ext):
            normalized = normalized[: -len(ext)]
    normalized = re.sub(r"_[A-Za-z0-9_]+$", "", normalized)

    # Прямой маппинг
    canonical_key = data.normalized_map.get(normalized)
    if canonical_key and canonical_key in data.raw_details:
        return data.raw_details[canonical_key]

    # Fallback reverse-map по basename
    base_name = normalized.split("/", 1)[-1]
    for key in data.reverse_map:
        if base_name.endswith(key) or (key and base_name == key):
            rd = data.raw_details.get(data.reverse_map[key])
            if rd:
                return rd

    return None


def clamp_context(raw: int | None, limit: int | None) -> int | None:
    """Ограничивает контекст заданным максимумом. Без limit — без изменений."""
    if raw is None:
        return None
    return min(raw, limit) if limit else raw


def _is_reasoning_model(model_id: str) -> bool:
    name = model_id.lower()
    return "reasoning" in name or "thinking" in name


def _detect_provider_type(url: str) -> str:
    lower = url.lower()
    if "/api/v1/" in lower:
        return "lmstudio"
    return "openai_compatible"


# ============================================================================
# Storage реализации
# ============================================================================
class PiStorage(Storage[dict]):
    def read(self) -> dict:
        if PI_MODELS.exists():
            return read_jsonc(PI_MODELS)
        return {"providers": {}}

    def write(self, data: dict) -> None:
        write_json(PI_MODELS, data)


class KiloStorage(Storage[dict]):
    def read(self) -> dict:
        if not KILO_CONFIG.exists():
            return {}
        return read_jsonc(KILO_CONFIG)

    def write(self, data: dict) -> None:
        write_json(KILO_CONFIG, data)


class OpenCodeStorage(Storage[dict]):
    def read(self) -> dict:
        if not OPENCODE_CONFIG.exists():
            return {}
        return read_jsonc(OPENCODE_CONFIG)

    def write(self, data: dict) -> None:
        write_json(OPENCODE_CONFIG, data)


class ZedStorage(Storage[dict]):
    def read(self) -> dict:
        if not ZED_SETTINGS.exists():
            return {}
        return read_jsonc(ZED_SETTINGS)

    def write(self, data: dict) -> None:
        write_json(ZED_SETTINGS, data)


class VSCodeStorage(Storage[list]):
    """VS Code chatLanguageModels — это list, а не dict."""
    def __init__(self, path: Path | None = None):
        self.path = path or _find_chat_models_path()

    def read(self) -> list:
        if self.path.exists():
            raw = self.path.read_text(encoding="utf-8")
            cleaned = strip_jsonc_comments(raw)
            if not cleaned.strip():
                return []
            return json.loads(cleaned)
        return []

    def write(self, data: list) -> None:
        write_json(self.path, data)


def _find_chat_models_path() -> Path:
    if CODE_CHAT_MODELS.exists():
        return CODE_CHAT_MODELS
    linux_path = CODE_USER_LINUX_FOLDER / "chatLanguageModels.json"
    if linux_path.exists():
        return linux_path
    CODE_USER_FOLDER.mkdir(parents=True, exist_ok=True)
    return CODE_CHAT_MODELS


# ============================================================================
# ProviderAccessor реализации
# ============================================================================
class PiProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        return config.setdefault("providers", {}).setdefault(key, {
            "baseUrl": "", "api": "openai-completions", "apiKey": "", "models": []
        })


class KiloProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        return config.setdefault("provider", {}).setdefault(key, {
            "name": key.capitalize(),
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": ""},
            "models": {},
        })


class OpenCodeProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        return config.setdefault("provider", {}).setdefault(key, {
            "name": key.capitalize(),
            "api": "openai-completions",
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": ""},
            "models": {},
        })


class ZedProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        language_models = config.setdefault("language_models", {})
        if key in ZED_PROVIDER_MAP:
            return language_models.setdefault(ZED_PROVIDER_MAP[key], {
                "api_url": "", "available_models": []
            })
        else:
            return language_models.setdefault("openai_compatible", {}).setdefault(key, {
                "api_url": "", "available_models": []
            })


# ============================================================================
# ModelBuilder реализации
# ============================================================================
class PiModelBuilder:
    def create(self, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> dict:
        pi_ctx = clamp_context(rd.get('max_context_length') if rd else 128000, max_context)
        input_types = ["text"]
        if caps.get("vision"):
            input_types.append("image")
        return {
            "id": model_id,
            "reasoning": _is_reasoning_model(model_id),
            "toolCalling": True,
            "input": input_types,
            "contextWindow": pi_ctx,
            "maxTokens": pi_ctx // 2,
        }

    def update(self, existing: dict, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> bool:
        needs_update = False
        want_reasoning = _is_reasoning_model(model_id)
        if existing.get("reasoning") != want_reasoning:
            existing["reasoning"] = want_reasoning
            needs_update = True

        input_types = ["text"]
        if caps.get("vision"):
            input_types.append("image")
        if set(existing.get("input", [])) != set(input_types):
            existing["input"] = input_types
            needs_update = True

        pi_ctx = clamp_context(rd.get('max_context_length') if rd else 128000, max_context)
        if existing.get('contextWindow') != pi_ctx:
            existing['contextWindow'] = pi_ctx
            needs_update = True
        if existing.get('maxTokens') != (pi_ctx // 2):
            existing['maxTokens'] = pi_ctx // 2
            needs_update = True

        return needs_update


class KiloModelBuilder:
    def create(self, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> dict:
        return {
            "name": model_id,
            "reasoning": caps.get("tools", True),
        }

    def update(self, existing: dict, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> bool:
        needs_update = False
        if existing.get("reasoning") != caps.get("tools", True):
            existing["reasoning"] = caps.get("tools", True)
            needs_update = True
        return needs_update


class OpenCodeModelBuilder:
    def create(self, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> dict:
        oc_ctx = clamp_context(rd.get('max_context_length') if rd else 128000, max_context)
        modalities = {
            "input": ["image", "text"] if caps.get("vision") else ["text"],
            "output": ["text"],
        }
        return {
            "name": model_id,
            "modalities": modalities,
            "limit": {"context": oc_ctx, "output": oc_ctx // 2},
        }

    def update(self, existing: dict, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> bool:
        needs_update = False
        if existing.get("name") != model_id:
            existing["name"] = model_id
            needs_update = True

        modalities = {
            "input": ["image", "text"] if caps.get("vision") else ["text"],
            "output": ["text"],
        }
        if existing.get("modalities") != modalities:
            existing["modalities"] = modalities
            needs_update = True

        oc_ctx = clamp_context(rd.get('max_context_length') if rd else 128000, max_context)
        existing_limit = existing.get("limit", {})
        if (existing_limit.get("context") != oc_ctx) or (existing_limit.get("output") != oc_ctx // 2):
            existing["limit"] = {"context": oc_ctx, "output": oc_ctx // 2}
            needs_update = True

        return needs_update


class ZedModelBuilder:
    def create(self, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> dict:
        zed_max = clamp_context(rd.get('max_context_length') if rd else 200000, max_context)
        return {
            "name": model_id,
            "display_name": model_id.split("/")[-1],
            "max_tokens": zed_max,
            "max_completion_tokens": zed_max,
            "supports_tool_calls": caps.get("tools", True),
            "supports_images": caps.get("vision", True),
        }

    def update(self, existing: dict, model_id: str, caps: dict, rd: dict | None, max_context: int | None = None) -> bool:
        needs_update = False
        if existing.get("supports_tool_calls") != caps["tools"]:
            existing["supports_tool_calls"] = caps["tools"]
            needs_update = True
        if existing.get("supports_images") != caps["vision"]:
            existing["supports_images"] = caps["vision"]
            needs_update = True
        if existing.get("display_name") != model_id.split("/")[-1]:
            existing["display_name"] = model_id.split("/")[-1]
            needs_update = True

        zed_max = clamp_context(rd.get('max_context_length') if rd else 200000, max_context)
        if existing.get('max_tokens') != zed_max:
            existing['max_tokens'] = zed_max
            needs_update = True
        if existing.get('max_completion_tokens') != zed_max:
            existing['max_completion_tokens'] = zed_max
            needs_update = True

        return needs_update


# ============================================================================
# Schema-конфигурации для каждого syncer'а
# ============================================================================
PI_SCHEMA = Schema(
    storage=PiStorage(),
    accessor=PiProviderAccessor(),
    builder=PiModelBuilder(),
    name="pi",
)

KILO_SCHEMA = Schema(
    storage=KiloStorage(),
    accessor=KiloProviderAccessor(),
    builder=KiloModelBuilder(),
    provider_map=KILO_PROVIDER_MAP,
    name="kilo",
)

OPENCODE_SCHEMA = Schema(
    storage=OpenCodeStorage(),
    accessor=OpenCodeProviderAccessor(),
    builder=OpenCodeModelBuilder(),
    name="opencode",
)

ZED_SCHEMA = Schema(
    storage=ZedStorage(),
    accessor=ZedProviderAccessor(),
    builder=ZedModelBuilder(),
    name="zed",
)


# ============================================================================
# Единый engine синхронизации
# ============================================================================
def sync_provider(schema: Schema, provider_name: str, cfg: dict, 
                  data: ProviderData, ctx: SyncContext) -> tuple[int, int, int]:
    """Синхронизирует модели для одного провайдера в один конфиг.

    DRY: одна функция для всех syncer'ов.
    """
    config = schema.storage.read()

    key = schema.provider_map.get(provider_name, provider_name)
    provider = schema.accessor.get_provider(config, key)

    # URL провайдера
    if "baseUrl" in provider:
        provider["baseUrl"] = cfg.get("url", "")
    elif "options" in provider:
        provider.setdefault("options", {})["baseURL"] = cfg.get("url", "")

    # API key
    if "apiKey" in provider:
        expected_key = cfg.get("key", "")
        if not expected_key or expected_key.lower() in {"undefined", "null", "none"}:
            expected_key = PI_API_KEY_DEFAULTS.get(provider_name, "")
        provider["apiKey"] = expected_key

    active_ids = {m for m in data.model_ids if not m.startswith("text-embedding")}
    added = 0
    updated = 0

    for model_id in data.model_ids:
        if model_id.startswith("text-embedding"):
            continue

        caps = ctx.capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        rd = resolve_model_details(model_id, data)

        # Override capabilities с LM Studio extended API данных
        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])

        # Получаем существующую модель
        existing = _get_model(provider, model_id)

        if existing:
            if schema.builder.update(existing, model_id, caps, rd, ctx.max_context):
                logger.info("  %s (%s): ~%s", schema.name or type(schema.builder).__name__, provider_name, model_id)
                updated += 1
        else:
            _set_model(provider, model_id, schema.builder.create(model_id, caps, rd, ctx.max_context))
            logger.info("  %s (%s): +%s", schema.name or type(schema.builder).__name__, provider_name, model_id)
            added += 1

    # Cleanup: удаляем устаревшие модели
    removed = _cleanup_models(provider, active_ids)

    schema.storage.write(config)
    return added, updated, removed


def _get_model(provider: dict, model_id: str) -> dict | None:
    """Получает модель из провайдера (разные форматы)."""
    # PI, Zed: list
    for key in ("models", "available_models"):
        models = provider.get(key, [])
        if isinstance(models, list):
            for m in models:
                if isinstance(m, dict) and (m.get("id") == model_id or m.get("name") == model_id):
                    return m
    # Kilo, OpenCode: dict
    models = provider.get("models", {})
    if isinstance(models, dict):
        return models.get(model_id)
    return None


def _set_model(provider: dict, model_id: str, model_data: dict) -> None:
    """Установить модель в провайдере (разные форматы)."""
    # PI, Zed: list
    for key in ("models", "available_models"):
        if key in provider:
            models = provider[key]
            if isinstance(models, list):
                # Проверяем, нет ли уже
                for m in models:
                    if isinstance(m, dict) and (m.get("id") == model_id or m.get("name") == model_id):
                        return  # уже есть
                models.append(model_data)
                return
    # Kilo, OpenCode: dict
    if "models" in provider:
        models = provider["models"]
        if isinstance(models, dict):
            models[model_id] = model_data


def _cleanup_models(provider: dict, active_ids: set[str]) -> int:
    """Удаляет устаревшие модели. Возвращает число удалённых."""
    removed = 0

    # Kilo, OpenCode: dict models
    if "models" in provider and isinstance(provider["models"], dict):
        for model_id in list(provider["models"].keys()):
            if model_id not in active_ids:
                del provider["models"][model_id]
                logger.info("  cleanup (-%s)", model_id)
                removed += 1
        return removed

    # PI, Zed: list models / available_models
    for key in ("models", "available_models"):
        if key in provider and isinstance(provider[key], list):
            to_remove = []
            for m in provider[key]:
                if isinstance(m, dict):
                    mid = m.get("id") or m.get("name")
                    if mid and mid not in active_ids:
                        to_remove.append(m)
            for m in to_remove:
                provider[key].remove(m)
                removed += 1
            break  # только один list может быть

    return removed


# ============================================================================
# VS Code sync (отдельная функция — свой формат данных)
# ============================================================================
PI_API_KEY_DEFAULTS = {
    "lmstudio": "lm-studio",
    "local-lms": "none",
}


def sync_vscode(provider_name: str, cfg: dict, data: ProviderData, 
                ctx: SyncContext) -> tuple[int, int, int]:
    """Синхронизирует модели в VS Code chatLanguageModels.json.

    Отдельная функция, т.к. формат — list[dict], а не dict.
    """
    models_path = _find_chat_models_path()

    data_list = models_path.read_text(encoding="utf-8") if models_path.exists() else "[]"
    cleaned = strip_jsonc_comments(data_list)
    if not cleaned.strip():
        data_list_parsed: list = []
    else:
        data_list_parsed = json.loads(cleaned)

    # Находим провайдера по name
    target = None
    for p in data_list_parsed:
        if isinstance(p, dict) and p.get("name") == provider_name:
            target = p
            break

    if not target:
        target = {
            "name": provider_name,
            "vendor": "customendpoint",
            "apiType": "messages",
            "models": [],
        }
        api_key = cfg.get("key")
        if not api_key:
            target["apiKey"] = f"$input:chat.lm.secret.-{hashlib.md5(provider_name.encode()).hexdigest()[:8]}"
        else:
            target["apiKey"] = f"$input:chat.lm.secret.-{hashlib.md5(api_key.encode()).hexdigest()[:8]}"
        data_list_parsed.append(target)

    active_ids = {m for m in data.model_ids if not m.startswith("text-embedding")}
    added = 0
    updated = 0

    for model_id in data.model_ids:
        if model_id.startswith("text-embedding"):
            continue

        caps = ctx.capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        rd = resolve_model_details(model_id, data)

        if rd:
            if rd.get('vision') is not None:
                caps['vision'] = bool(rd['vision'])
            if rd.get('tools') is not None:
                caps['tools'] = bool(rd['tools'])

        existing = next((m for m in target.get("models", []) if m.get("id") == model_id), None)

        mcl = clamp_context(rd.get('max_context_length') if rd else 128000, ctx.max_context)

        if existing:
            needs_update = False
            if existing.get("toolCalling") != caps.get("tools", True):
                existing["toolCalling"] = caps.get("tools", True)
                needs_update = True
            if existing.get("vision") != caps.get("vision", True):
                existing["vision"] = caps.get("vision", True)
                needs_update = True
            if existing.get('maxInputTokens') != mcl:
                existing['maxInputTokens'] = mcl
                needs_update = True
            if existing.get('maxOutputTokens') != (mcl // 2):
                existing['maxOutputTokens'] = mcl // 2
                needs_update = True
            if needs_update:
                logger.info("  VSCode (%s): ~%s", provider_name, model_id)
                updated += 1
        else:
            target.setdefault("models", []).append({
                "id": model_id,
                "name": model_id,
                "url": cfg["url"],
                "toolCalling": caps.get("tools", True),
                "vision": caps.get("vision", True),
                "maxInputTokens": mcl,
                "maxOutputTokens": mcl // 2,
            })
            logger.info("  VSCode (%s): +%s", provider_name, model_id)
            added += 1

    # Cleanup
    removed = 0
    for model in list(target.get("models", [])):
        if model.get("id") not in active_ids:
            target["models"].remove(model)
            logger.info("  VSCode (%s): -%s", provider_name, model.get('id'))
            removed += 1

    write_json(models_path, data_list_parsed)
    return added, updated, removed


# ============================================================================
# VS Code profiles sync (копирование конфига)
# ============================================================================
# ============================================================================
# Cleanup — удаление моделей удалённых провайдеров
# ============================================================================

def cleanup_stale_models(active_providers: set[str]) -> tuple[int, int, int]:
    """Удаляет модели провайдеров, которых нет в active_providers.
    
    Возвращает (added, updated, removed).
    """
    total_added = 0
    total_updated = 0
    total_removed = 0

    # PI
    pi_path = PI_MODELS
    if pi_path.exists():
        data = json.loads(pi_path.read_text(encoding="utf-8"))
        providers = data.get("providers", {})
        stale = [p for p in providers if p not in active_providers]
        for p in stale:
            logger.info("  pi: удаление провайдера %s (%d моделей)", p, len(providers[p].get("models", [])))
            del providers[p]
            total_removed += 1
        if stale:
            pi_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Kilo
    kilo_path = KILO_CONFIG
    if kilo_path.exists():
        raw = kilo_path.read_text(encoding="utf-8")
        cleaned = strip_jsonc_comments(raw)
        data = json.loads(cleaned)
        provider = data.get("provider", {})
        stale = [p for p in provider if isinstance(provider[p], dict) and "models" in provider[p] and p not in active_providers]
        for p in stale:
            logger.info("  kilo: удаление провайдера %s", p)
            del provider[p]
            total_removed += 1
        if stale:
            tmp = kilo_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(kilo_path)

    # OpenCode
    oc_path = OPENCODE_CONFIG
    if oc_path.exists():
        raw = oc_path.read_text(encoding="utf-8")
        cleaned = strip_jsonc_comments(raw)
        data = json.loads(cleaned)
        provider = data.get("provider", {})
        stale = [p for p in provider if isinstance(provider[p], dict) and "models" in provider[p] and p not in active_providers]
        for p in stale:
            logger.info("  opencode: удаление провайдера %s", p)
            del provider[p]
            total_removed += 1
        if stale:
            tmp = oc_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(oc_path)

    # Zed
    zed_path = ZED_SETTINGS
    if zed_path.exists():
        data = json.loads(zed_path.read_text(encoding="utf-8"))
        lm = data.get("language_models", {})
        oai = lm.get("openai_compatible", {})
        stale = [p for p in oai if "available_models" in oai[p] and p not in active_providers]
        for p in stale:
            logger.info("  zed: удаление провайдера %s", p)
            del oai[p]
            total_removed += 1
        if stale:
            tmp = zed_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(zed_path)

    # VS Code — chatLanguageModels.json (list format)
    vscode_path = CODE_CHAT_MODELS
    if vscode_path.exists():
        raw = vscode_path.read_text(encoding="utf-8")
        cleaned = strip_jsonc_comments(raw)
        data = json.loads(cleaned)
        stale_ids = [m["id"] for m in data if isinstance(m, dict) and "providerId" in m and m["providerId"] not in active_providers]
        for mid in stale_ids:
            logger.info("  vscode: удаление модели %s", mid)
            data = [m for m in data if not (isinstance(m, dict) and m.get("id") == mid)]
            total_removed += 1
        if stale_ids:
            tmp = vscode_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(vscode_path)

    return total_added, total_updated, total_removed


def sync_vscode_profiles() -> int:
    """Копирует chatLanguageModels.json из основного конфига во все профили VS Code."""
    profiles_dir = CODE_USER_FOLDER / "profiles"
    if not profiles_dir.exists():
        return 0

    profile_uuids = [
        p.name for p in profiles_dir.iterdir()
        if p.is_dir() and re.match(r"^[0-9a-f\-]{8,}$", p.name)
    ]

    if not profile_uuids:
        return 0

    primary_chat_models = CODE_USER_FOLDER / "chatLanguageModels.json"
    if not primary_chat_models.exists():
        return 0

    raw = primary_chat_models.read_text(encoding="utf-8")
    cleaned = strip_jsonc_comments(raw)
    if not cleaned.strip():
        return 0

    source_data = json.loads(cleaned)
    copied = 0

    for uuid in profile_uuids:
        dest_path = profiles_dir / uuid / "chatLanguageModels.json"
        try:
            tmp = dest_path.with_suffix('.tmp')
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(source_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(dest_path)
            copied += 1
        except Exception as e:
            logger.warning("sync_profiles: ошибка при записи %s: %s", dest_path, e)
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass

    return copied


# ============================================================================
# Fetch models (обёртка, возвращает ProviderData)
# ============================================================================
REQUEST_TIMEOUT = 10


def fetch_models(url: str, api_key: str = "") -> ProviderData:
    """Fetch модели с провайдера. Возвращает ProviderData."""
    base_url = url.rstrip("/")
    provider_type = _detect_provider_type(url)

    # Standard OpenAI-compatible endpoint
    if provider_type == "lmstudio":
        openai_url = f"{base_url}/v1/models"
    else:
        openai_url = f"{base_url}/models"

    model_ids = []
    try:
        req = urllib.request.Request(openai_url)
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept-Charset", "utf-8")

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw_data = resp.read().decode('utf-8', errors='ignore')
            data = json.loads(raw_data)
        model_ids = [m["id"] for m in data.get("data", [])]
    except Exception as e:
        logger.warning("  warn: не удалось получить модели с %s: %s", openai_url, e)

    # LM Studio extended API
    raw_details: dict = {}
    normalized_map: dict[str, str] = {}
    reverse_map: dict[str, str] = {}

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
        logger.info("  [api/v1] нет расширенных данных с %s", extended_url)
    else:
        if raw_details and normalized_map:
            logger.info("  [api/v1] получено %d моделей с расширенными свойствами", len(raw_details))

    return ProviderData(
        model_ids=tuple(model_ids),
        raw_details=raw_details,
        normalized_map=normalized_map,
        reverse_map=reverse_map,
    )


def _parse_lmstudio_details(response_data: dict) -> tuple[dict, dict, dict]:
    """Парсит LM Studio extended API response."""
    result: dict = {}
    normalized_map: dict[str, str] = {}
    reverse_map: dict[str, str] = {}

    for m in response_data.get("models", []):
        key = m.get("key")
        if not key:
            continue

        caps = m.get("capabilities", {})
        quantization = m.get("quantization", {})

        rd = {
            "vision": caps.get("vision"),
            "tools": caps.get("trained_for_tool_use", caps.get("tool_use")),
            "architecture": m.get("architecture", ""),
            "quantization": quantization.get("name") if isinstance(quantization, dict) else str(quantization),
            "size_bytes": m.get("size_bytes"),
            "max_context_length": m.get("max_context_length"),
        }

        result[key] = rd

        # normalized_map: norm_v1_id -> canonical_key
        normalized = key.lower()
        for ext in [".gguf", ".bin", ".mlx"]:
            if normalized.endswith(ext):
                normalized = normalized[: -len(ext)]
        normalized = re.sub(r"_[A-Za-z0-9_]+$", "", normalized)
        normalized_map[normalized] = key

        # reverse_map: basename -> canonical_key
        base_name = normalized.split("/", 1)[-1]
        if "/" in key and base_name not in normalized_map:
            reverse_map[base_name] = key

    return result, normalized_map, reverse_map


# ============================================================================
# Config parsing utilities
# ============================================================================
def load_capabilities(path: Path = MODEL_CAPABILITIES_YAML) -> dict[str, dict]:
    """Загружает capabilities из YAML."""
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    capabilities = {}
    current_model = None

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
            current_model = model_match.group(2).strip()
            capabilities[current_model] = {}
            continue

        field_match = re.match(r"^(\s+)([^:\s][^:]*):\s*(.+)$", line)
        if field_match and current_model is not None:
            key = field_match.group(2).strip()
            value = field_match.group(3).strip().lower()
            if value in {"true", "yes", "y", "1"}:
                capabilities[current_model][key] = True
            elif value in {"false", "no", "n", "0"}:
                capabilities[current_model][key] = False

    return capabilities


def parse_providers_conf() -> dict[str, dict]:
    """Парсит providers.conf и возвращает {имя: {url, key}}."""
    if not PROVIDERS_CONF.exists():
        logger.error("providers.conf не найден: %s", PROVIDERS_CONF)
        return {}

    config = configparser.ConfigParser()
    config.read(PROVIDERS_CONF)

    providers = {}
    for section in config.sections():
        url_raw = config.get(section, "url", fallback="").strip().rstrip("/")
        if not url_raw or url_raw.lower() in {"undefined", "null", "none"}:
            logger.warning("  пропуск %s: неверный URL", section)
            continue

        key_raw = config.get(section, "key", fallback="").strip()
        if key_raw.lower() in {"undefined", "null", "none"}:
            key_raw = ""

        providers[section] = {"url": url_raw, "key": key_raw}

    return providers


# ============================================================================
# Main orchestration
# ============================================================================
def main() -> None:
    args = SyncArgs.from_cli()
    setup_logging(args.verbose)

    logger.info("Читаю провайдеры из %s", PROVIDERS_CONF)

    # Загружаем capabilities
    if MODEL_CAPABILITIES_YAML.exists():
        capabilities = load_capabilities()
        logger.info("Загружено %d моделей из YAML capabilities", len(capabilities))
    else:
        capabilities = {}
        logger.info("Не найден %s, capabilities не загружены", MODEL_CAPABILITIES_YAML)

    providers = parse_providers_conf()
    if not providers:
        logger.error("Нет провайдеров для синхронизации")
        return

    # Schema'и для sync_provider
    schemas = [PI_SCHEMA, KILO_SCHEMA, OPENCODE_SCHEMA, ZED_SCHEMA]

    total_added = 0
    total_updated = 0
    total_removed = 0

    for provider_name, cfg in providers.items():
        # Фильтр по провайдеру (если задан --provider)
        if args.provider_filter and provider_name != args.provider_filter:
            continue

        logger.info("\nОбработка провайдера: %s (%s)", provider_name, cfg['url'])

        data = fetch_models(cfg["url"], cfg.get("key", ""))
        if not data.model_ids:
            logger.info("  Нет моделей для %s", provider_name)
            continue

        ctx = SyncContext(
            provider_name=provider_name,
            provider_cfg=cfg,
            capabilities=capabilities,
            max_context=args.max_context,
        )

        # Sync через engine (DRY: один вызов для всех schema'ей)
        for schema in schemas:
            added, updated, removed = sync_provider(schema, provider_name, cfg, data, ctx)
            total_added += added
            total_updated += updated
            total_removed += removed

        # VS Code (отдельная функция — свой формат)
        added, updated, removed = sync_vscode(provider_name, cfg, data, ctx)
        total_added += added
        total_updated += updated
        total_removed += removed

    logger.info("\nИтого: добавлено %d, обновлено %d, удалено %d моделей",
                total_added, total_updated, total_removed)

    # Cleanup — удаление удалённых провайдеров
    if args.cleanup:
        active_set = set(providers.keys())
        logger.info("\nCleanup: удаление моделей провайдеров, которых нет в providers.conf")
        ca, cu, cr = cleanup_stale_models(active_set)
        total_added += ca
        total_updated += cu
        total_removed += cr
        logger.info("Cleanup: добавлено %d, обновлено %d, удалено %d", ca, cu, cr)

    # Копируем chatLanguageModels во все профили VS Code
    copied = sync_vscode_profiles()
    logger.info("Профили VS Code: скопировано %d", copied)


if __name__ == "__main__":
    main()
