#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.
#
#   ./install.sh                     # спросит, запускать ли bootstrap
#   ./install.sh -y                  # bootstrap без вопроса
#   ./install.sh --no-bootstrap      # только конфиги shell'а

set -euxo pipefail

# Запуск из любой директории: переходим в корень dotfiles
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUN_BOOTSTRAP=false
for arg in "$@"; do
  case "$arg" in
    -y | --yes | --bootstrap) RUN_BOOTSTRAP=true ;;
    --no-bootstrap) RUN_BOOTSTRAP=false ;;
    *) echo "ℹ️ Неизвестный аргумент: $arg" ;;
  esac
done

if ! $RUN_BOOTSTRAP; then
  read -r -p "Запустить ./scripts/bootstrap.sh --install (zsh, bat, tmux, neovim, uv, prep)? [y/N]: " confirm || confirm=""
  if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    RUN_BOOTSTRAP=true
  fi
fi

# Extracted clipboard helper installer
./installers/install_clipboard_helpers.sh || true

CONFIGS=(
  shell/bash_tools
  shell/zsh_aliases
  shell/zsh_tools
  shell/gw
  shell/agent-runner.sh
  shell/zshenv
  shell/.zshrc
  shell/project_clean.sh
  shell/charset_fix.sh
  shell/shell_prompt
  shell/minimal.zshrc
  shell/nvmv.sh
  installers/install-oh-my-zsh.sh
  installers/install_uv.sh
  installers/install_prep.sh
  git/git_checkout_branch.sh
  git/git_delete_branch.sh
  tmux/tmux_session_selector.sh
  tmux/create_tmux_session.sh
  utils/commit.sh
  utils/fvm_tools.sh
  utils/clean.sh
)

# Configs that should be copied to the home directory.
CONFIGS_HOME_DIR=(
  tmux/.tmux.conf
  shell/.zshrc
  shell/.bashrc
)

# Конфиги копируются всегда — раньше это зависело от "$#" -eq 0,
# из-за чего `./install.sh y` ничего не устанавливал.
for i in "${CONFIGS_HOME_DIR[@]}"; do
  if [ "$i" = "shell/.zshrc" ]; then
    # Собираем .zshrc с флагом oh-my-zsh (иначе ветка if в .zshrc не сработает)
    { printf "export USE_OH_MY_ZSH='true'\n"; cat shell/minimal.zshrc; cat shell/.zshrc; } > ~/.zshrc
  else
    cp -rvf "${i}" ~/
  fi
done

mkdir -p ~/.dotfiles
for i in "${CONFIGS[@]}"; do
  if [ ! -f "${i}" ]; then
    echo "⚠️  пропускаем ${i} — файла нет в репозитории" >&2
    continue
  fi
  cp -rvf "${i}" ~/.dotfiles/
done

./installers/install-oh-my-zsh.sh || true
./installers/install_fzf.sh || true

# uv + команда prep — устанавливаются в любом случае
./installers/install_prep.sh

if $RUN_BOOTSTRAP; then
  ./scripts/bootstrap.sh --install || echo "⚠️ bootstrap завершился с ошибкой"
fi

echo "✅ Готово. Перезагрузите shell:  reload-zsh"
echo "   Проверка:  prep --help"

exit 0
