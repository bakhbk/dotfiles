# Dotfiles

Configuration files and useful scripts for OS X and Linux.

## Installation

```bash
# To install common configuration files on localhost do:
$ ./install.sh              # спросит, запускать ли bootstrap
$ ./install.sh -y           # bootstrap сразу (zsh, bat, tmux, neovim, uv, prep)
$ ./install.sh --no-bootstrap   # только конфиги shell'а
```

Конфиги копируются в `~/.dotfiles`, а `.zshrc`/`.bashrc`/`.tmux.conf` — в `~/`.
Это происходит **независимо от аргументов** скрипта.

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

```bash
# Только uv/prep, без остального, без остального
$ ./installers/install_uv.sh
$ ./installers/install_prep.sh
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
