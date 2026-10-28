# Dotfiles

Configuration files and useful scripts for OS X and Linux.

## Installation

```bash
$ ./install.sh                # каждый раз спрашивает (подсказывает прошлый выбор)
$ ./install.sh -y             # bootstrap + всё без вопросов
$ ./install.sh --no-bootstrap # только конфиги shell'а
```

Конфиги копируются в `~/.dotfiles`, а `.zshrc`/`.bashrc`/`.tmux.conf` — в `~/`.
Это происходит **независимо от аргументов** скрипта.

### Один «да» — и больше ни один вложенный скрипт не спрашивает

Во время работы `install.sh` экспортирует для всех вложенных install'er'ов:

| Переменная | Эффект |
|---|---|
| `DOTFILES_ASSUME_YES=1` | все вложенные install'er'ы работают без вопросов |
| `HOMEBREW_NO_ASK=1` | Homebrew не спрашивает «Do you want to proceed with the installation? [y/n]» |
| `HOMEBREW_NO_INSTALL_CLEANUP=1` | без лишней уборки Cellar |
| `DEBIAN_FRONTEND=noninteractive` | apt не интерактивит |

Вопрос про bootstrap задаётся **при каждом запуске** `./install.sh`, чтобы решение
можно было поменять. Предыдущий выбор пишется в `~/.dotfiles/install.conf`
(`bootstrap=y|n`) и используется только как default подсказки: «(в прошлый раз: y)».
Helper-функция `ask_yes` находится в `installers/noninteractive.sh` — используйте её
во всех новых скриптах установки.

### AI-агенты: команда `prep`

`install.sh` всегда устанавливает `uv` и настраивает команду `prep`
(синхронизация моделей между pi, kilo, opencode, Zed, VS Code):

```bash
prep                # обычный запуск
prep-fast           # --max-context 8000
prep-code           # --max-context 16000
prep-deep           # --max-context 32000
prep-big            # --max-context 64000
prep-clean          # --cleanup
```

`prep` работает и в zsh, и в bash: создаётся wrapper `~/.local/bin/prep`,
а путь к репозиторию берётся из `~/.dotfiles/dotfiles.env` (генерируется
`installers/install_prep.sh`). Подробнее — `scripts/prep-agents/README.md`.

Если `prep` не работает, диагностика одной командой:

```bash
$ ./installers/doctor.sh     # проверит uv, PATH, prep-agents.py, providers.conf
```

`install_uv.sh` устойчив к lock'ам Homebrew ("A `brew install uv` process has already
locked /usr/local/Cellar/uv"): он повторяет попытку 3 раза, затем ставит uv через
официальный installer (в `~/.local/bin`), затем через `pip`. Сам `prep` при
отсутствии `uv` падает не с ошибкой, а запускается на `python3`.

```bash
# Только uv/prep, без остального, без остального
$ ./installers/install_uv.sh
$ ./installers/install_prep.sh
```

### Проверка установки

```bash
$ ./scripts/tests/test_install.sh   # 12 проверок: prep, uv, отсутствие prompts
```

## Docker/OrbStack

### Install OrbStack (recommended for macOS)
```bash
# Install or update OrbStack with docker compose support
$ ./scripts/install_orbstack.sh
# or
$ ./.install_orbstack.sh
```

### Remove Docker Desktop (before installing OrbStack)
```bash
# Remove Docker Desktop cleanly
$ ./.remove_docker_desktop.sh
```

See [ORBSTACK.md](ORBSTACK.md) for detailed information.

Based on [these sources](https://github.com/alkurbatov/dotfiles)
