# prep-agents

Подготовка AI-агентов к работе: синхронизация моделей из провайдеров во все поддерживаемые инструменты.

## 🚀 Быстрый старт

### Алиас `prep`

В `~/.zsh_aliases` добавлен алиас:

```bash
prep                    # тихий режим (только ошибки)
prep -v                 # verbose (все логи)
prep --max-context 80000
prep --provider START
```

### Полный запуск

```bash
# Запуск без ограничений (как раньше)
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py

# С ограничением контекста 80k токенов
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --max-context 80000

# Только один провайдер
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --provider START

# Тихий режим (только ошибки)
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py -q

# Комбинация флагов
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --max-context 80000 --provider START -q
```

## 📋 Что делает

Читает провайдеры из `~/.config/dispatch/providers.conf` (формат INI), fetchит модели через OpenAI-compatible endpoint, и синхронизирует во все инструменты.

### Формат конфига провайдеров

```ini
[provider-name]
url=https://example.com/v1
key=sk-xxx
```

Каждая секция — один провайдер. `url` — endpoint, `key` — API ключ (или "none" для локальных).

### Маппинг провайдеров

Некоторые инструменты используют другие имена для провайдеров. Маппинг задаётся в `provider_map`:

```python
PROVIDER_MAP = {
    # "имя_из_конфига": "ключ_в_конфиге",
}
```

| Инструмент | Файл | Статус |
|------------|------|--------|
| **pi** | `~/.pi/agent/models.json` | ✅ |
| **kilo** | `~/.config/kilo/kilo.jsonc` | ✅ |
| **opencode** | `~/.config/opencode/opencode.jsonc` | ✅ |
| **zed** | `~/.config/zed/settings.json` (language_models) | ✅ |
| **VS Code** | `~/Library/Application Support/Code/User/chatLanguageModels.json` | ✅ |
| **VS Code Profiles** | Копирование конфига во все профили | ✅ |

## 🏗 Архитектура

### Data-Driven Design

Скрипт следует принципу **data-driven**: единый engine `sync_provider()` работает со всеми инструментами через конфигурацию (Schema), а не через наследование.

```
┌─────────────────────────────────────────────────┐
│                    main()                       │
│  ┌──────────────┐  ┌──────────────────────┐     │
│  │ fetch_models │→ │   ProviderData       │     │
│  └──────────────┘  └──────────────────────┘     │
│                        ↓                        │
│  ┌──────────────┐  ┌──────────────────────┐     │
│  │   load_      │→ │   SyncContext        │     │
│  │ capabilities │  └──────────────────────┘     │
│  └──────────────┘               ↓               │
│  ┌────────────────────────────────────────┐     │
│  │     sync_provider(schema, ctx)         │     │
│  │  ┌──────────┐ ┌──────────┐ ┌────────┐  │     │
│  │  │ Storage  │ │Accessor  │ │Builder │  │     │
│  │  └──────────┘ └──────────┘ └────────┘  │     │
│  └────────────────────────────────────────┘     │
│              ↓    ↓    ↓    ↓    ↓              │
│           PI  Kilo OpenCode Zed VSCode          │
└─────────────────────────────────────────────────┘
```

### Компоненты

#### 1. Storage[T] — работа с файлами

```python
class PiStorage(Storage[dict]):
    def read(self) -> dict: ...   # читает models.json
    def write(self, data: dict): ...  # пишет models.json

class VSCodeStorage(Storage[list]):
    def read(self) -> list: ...   # читает chatLanguageModels.json (list!)
    def write(self, data: list): ...
```

**Принцип:** Каждый syncer имеет свой Storage, инкапсулирующий формат файла.

#### 2. ProviderAccessor — навигация по структуре конфига

```python
class PiProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        return config.setdefault("providers", {}).setdefault(key, {...})

class ZedProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        # Zed: language_models.openai_compatible[key] или language_models[lmstudio]
        ...
```

**Принцип:** Инкапсулирует различия в структуре конфигов.

#### 3. ModelBuilder — создание/обновление моделей

```python
class PiModelBuilder:
    def create(self, model_id, caps, rd, max_context) -> dict:
        return {"id": ..., "contextWindow": clamp(...), ...}

    def update(self, existing, model_id, caps, rd, max_context) -> bool:
        # обновляет поля, возвращает True если были изменения
        ...

class ZedModelBuilder:
    def create(self, model_id, caps, rd, max_context) -> dict:
        return {"name": ..., "max_tokens": clamp(...), ...}
```

**Принцип:** Каждый syncer определяет свою схему модели.

#### 4. Schema — сборка syncer'а

```python
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
    provider_map={"source-provider": "target-key", ...},  # маппинг имён провайдеров
    name="kilo",
)
```

#### 5. Engine — единая функция синхронизации

```python
def sync_provider(schema: Schema, provider_name: str, cfg: dict, 
                  data: ProviderData, ctx: SyncContext) -> tuple[int, int, int]:
    """Добавить/обновить/удалить модели. Один раз для всех syncer'ов."""
    config = schema.storage.read()
    provider = schema.accessor.get_provider(config, key)
    
    for model_id in data.model_ids:
        caps = ctx.capabilities.get(model_id, CAPABILITIES_DEFAULTS)
        rd = resolve_model_details(model_id, data)
        
        existing = _get_model(provider, model_id)
        if existing:
            schema.builder.update(existing, model_id, caps, rd, ctx.max_context)
        else:
            _set_model(provider, model_id, schema.builder.create(model_id, caps, rd, ctx.max_context))
    
    _cleanup_models(provider, active_ids)
    schema.storage.write(config)
```

## 📐 Принципы проектирования

### SOLID

| Принцип | Как реализовано |
|---------|-----------------|
| **S**RP | Storage/Accessor/Builder разделены по ответственности |
| **O**CP | Новый syncer = новый Schema, без изменения engine |
| **L**SP | Все builders реализуют ModelBuilder протокол |
| **I**SP | Протоколы маленькие и специфичные (Storage, Accessor, Builder) |
| **D**IP | Зависят от абстракций (Protocols), не от конкретик |

### DRY

- `resolve_model_details()` — один раз для всех syncer'ов
- `sync_provider()` — один engine для всех syncer'ов
- `_get_model()`, `_set_model()`, `_cleanup_models()` — общие утилиты
- `clamp_context()` — одна функция ограничения контекста

### KISS

- Нет наследования классов
- Простые dataclass'и и протоколы
- Data-driven вместо магических строк

### YAGNI

- Нет оверхеда: только то что нужно
- VS Code sync — отдельная функция (свой формат)
- `sync_vscode_profiles()` — отдельная функция (копирование конфига)

## 🔧 Расширение

### Добавление нового syncer'а (например, Cursor)

**3 шага:**

#### 1. Storage

```python
class CursorStorage(Storage[dict]):
    def __init__(self, path=CURSOR_SETTINGS): self.path = path
    
    def read(self) -> dict:
        if not self.path.exists(): return {}
        return read_jsonc(self.path)
    
    def write(self, data: dict):
        write_json(self.path, data)
```

#### 2. ProviderAccessor

```python
class CursorProviderAccessor:
    def get_provider(self, config: dict, key: str) -> dict:
        # Cursor хранит модели иначе — адаптируем под его структуру
        return config.setdefault("providers", {}).setdefault(key, {
            "models": []  # или что там у Cursor
        })
```

#### 3. ModelBuilder

```python
class CursorModelBuilder:
    def create(self, model_id: str, caps: dict, rd: dict | None, 
               max_context: int | None = None) -> dict:
        ctx = clamp_context(rd.get('max_context_length') if rd else None, max_context) or 128000
        return {
            "id": model_id,
            "contextWindow": ctx,
            # ... Cursor-specific fields
        }
    
    def update(self, existing: dict, model_id: str, caps: dict, 
               rd: dict | None, max_context: int | None = None) -> bool:
        needs_update = False
        # ... обновляем поля
        return needs_update
```

#### 4. Регистрация в main()

```python
CURSOR_SCHEMA = Schema(
    storage=CursorStorage(),
    accessor=CursorProviderAccessor(),
    builder=CursorModelBuilder(),
    name="cursor",
)

# В main():
schemas = [PI_SCHEMA, KILO_SCHEMA, OPENCODE_SCHEMA, ZED_SCHEMA, CURSOR_SCHEMA]
```

**Итого: ~40 строк кода + 1 строка в main().**

### Добавление нового аргумента CLI

```python
@dataclass
class SyncArgs:
    max_context: int | None = None
    provider_filter: str | None = None
    quiet: bool = False
    dry_run: bool = False  # ← новое поле
    
    @classmethod
    def from_cli(cls) -> "SyncArgs":
        parser = argparse.ArgumentParser()
        parser.add_argument("--max-context", type=int)
        parser.add_argument("--provider")
        parser.add_argument("-q", "--quiet", action="store_true")
        parser.add_argument("--dry-run", action="store_true")  # ← новая строка
        args = parser.parse_args()
        return cls(**vars(args))
```

**Итого: 1 поле + 1 строка в from_cli().**

### Изменение логики clamp_context

```python
def clamp_context(raw: int | None, limit: int | None) -> int | None:
    if raw is None:
        return None
    # Новое правило: не меньше 32k
    return max(min(raw, limit) if limit else raw, 32000)
```

**Итого: 1 строка изменения — затронуты все syncer'ы.**

## 🚫 Чего не делать

### ❌ Не менять signature Protocol'ов

```python
# ПЛОХО: меняем протокол
class ModelBuilder(Protocol):
    def create(self, model_id, caps, rd, max_context, extra_param) -> dict: ...

# ХОРОШО: добавляем параметр с дефолтом
class ModelBuilder(Protocol):
    def create(self, model_id, caps, rd, max_context=None) -> dict: ...
```

### ❌ Не дублировать логику resolve_details

Если нужно изменить логику разрешения деталей модели — меняем `resolve_model_details()`, а не каждый syncer.

### ❌ Не использовать наследование для syncer'ов

```python
# ПЛОХО: хрупкое наследование
class BaseSyncer: ...
class PiSyncer(BaseSyncer): ...

# ХОРОШО: data-driven composition
PI_SCHEMA = Schema(storage=..., accessor=..., builder=...)
```

### ❌ Не хардкодить пути в engine

Пути должны быть в Storage, не в `sync_provider()`.

## 🧪 Тестирование

### Unit tests

```bash
cd scripts/prep-agents && python3 test_prep_agents.py
```

Все тесты работают в памяти — без файловой системы, без network.

### Coverage

| Компонент | Тестов |
|-----------|--------|
| clamp_context | 2 |
| resolve_model_details | 3 |
| Storage (Pi, Kilo) | 2 |
| ProviderAccessor (Pi, Kilo, Zed) | 4 |
| ModelBuilder (Pi, Kilo, OpenCode, Zed) | 7 |
| _get/set/cleanup models | 8 |
| sync_provider (PI, Zed, Kilo, OpenCode) | 7 |
| VS Code sync | 2 |
| Utils (capabilities, SyncArgs) | 2 |
| **Итого** | **38** |

### Integration tests

```bash
# С ограничением контекста
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --max-context 80000

# Проверка результатов
python3 -c "import json; d=json.load(open('/Users/b/.pi/agent/models.json')); print(d['providers']['START']['models'][0]['contextWindow'])"
# Ожидается: 80000

# Без ограничения (регрессия)
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py

# Проверка что контекст восстановился
python3 -c "import json; d=json.load(open('/Users/b/.pi/agent/models.json')); print(d['providers']['START']['models'][0]['contextWindow'])"
# Ожидается: 262144 (оригинал)
```

## 📊 Сравнение с sync-models.py

| Критерий | sync-models.py (старый) | prep-agents.py (новый) |
|----------|------------------------|----------------------|
| **Строк кода** | ~800 | ~750 (но чище) |
| **Функций sync** | 5 дублирующих | 1 engine + 5 схем |
| **DRY** | ❌ Дублирование resolve/cleanup | ✅ Единые утилиты |
| **Расширяемость** | ❌ Копировать 5 функций | ✅ Schema + 3 класса |
| **Тестируемость** | ❌ Зависит от файлов | ✅ Mock'и, in-memory |
| **SOLID** | ❌ Нарушен DIP | ✅ Полное соблюдение |
| **Регрессии** | ⚠️ Ручная проверка | ✅ 38 unit tests |

## 🔍 Отладка

### Включить подробный лог

```bash
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --provider START 2>&1 | grep -E "(pi|kilo|opencode|zed)"
```

### Проверить конкретный syncer

```bash
# Только PI
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --provider START 2>&1 | grep "pi (START)"

# Только Zed
uv run ~/dotfiles/scripts/prep-agents/prep-agents.py --provider START 2>&1 | grep "zed (START)"
```

### Проверить значения контекста

```bash
python3 -c "
import json

# PI
d = json.load(open('/Users/b/.pi/agent/models.json'))
print('PI:', d['providers']['START']['models'][0]['contextWindow'])

# OpenCode
d = json.load(open('/Users/b/.config/opencode/opencode.jsonc'))
print('OpenCode:', d['provider']['START']['models']['qwen/3.6']['limit']['context'])

# Zed
d = json.load(open('/Users/b/.config/zed/settings.json'))
print('Zed:', d['language_models']['openai_compatible']['START']['available_models'][0]['max_tokens'])

# VS Code
d = json.load(open('/Users/b/Library/Application Support/Code/User/chatLanguageModels.json'))
p=[p for p in d if p.get('name')=='START'][0]
print('VSCode:', p['models'][0]['maxInputTokens'])
"
```

## 📝 История версий

### v1.0 (текущая)
- ✅ Data-driven architecture
- ✅ SOLID principles
- ✅ 38 unit tests
- ✅ `--max-context` flag
- ✅ `--provider` filter
- ✅ `-q/--quiet` mode
- ✅ Logging через logging module
- ✅ Fallback: sync-models.py (без изменений)
