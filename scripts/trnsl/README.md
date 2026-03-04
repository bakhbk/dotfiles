# trnsl

CLI-переводчик текстовых файлов через локальный Ollama LLM.

## Установка

Алиас в `.zsh_aliases`:
```bash
alias trnsl='uv run ~/dotfiles/scripts/trnsl/trnsl.py'
```

После `./install.sh` команда `trnsl` доступна глобально.

## Использование

```bash
trnsl -ru path/to/file.md              # → file.tr.md рядом с оригиналом
trnsl -ru path/to/file.md output.md   # → output.md
trnsl --lang fr path/to/file.txt       # → file.tr.md на французском
```

## Флаги

| Флаг | Описание |
|------|----------|
| `-ru`, `-en`, `-fr`, `-de`, `-es`, `-zh`, `-ar` | Шорткат языка |
| `--lang LANG` | Язык (код или название) |
| `--model MODEL` | Ollama-модель (или `TRNSL_MODEL` env var) |

## Модель по умолчанию

`qwen2.5:7b` — переопределяется через env:
```bash
TRNSL_MODEL=llama3.2:3b trnsl -ru doc.md
```

## Поведение

- Файл разбивается на чанки по `\n\n` (мягкий лимит 2000 символов) — важно для больших документов
- Markdown-форматирование сохраняется; код-блоки не переводятся
- Перед перезаписью существующего output создаётся `.bak`
- Прогресс отображается через `rich`
