#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.
#
#   ./install.sh                # спрашивает каждый раз (подсказывает прошлый выбор)
#   ./install.sh -y             # bootstrap + всё без вопросов (non-interactive)
#   ./install.sh --no-bootstrap # только конфиги shell'а, без вопроса
#   ./install.sh --bootstrap    # bootstrap без вопроса

set -euxo pipefail

# Запуск из любой директории: переходим в корень dotfiles
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOTFILES_ASSUME_YES=0
BOOTSTRAP_CHOICE=""
for arg in "$@"; do
  case "$arg" in
    -y | --yes | --bootstrap)
      BOOTSTRAP_CHOICE=y
      DOTFILES_ASSUME_YES=1
      ;;
    --no-bootstrap)
      BOOTSTRAP_CHOICE=n
      DOTFILES_ASSUME_YES=1
      ;;
    *) echo "ℹ️ Неизвестный аргумент: $arg" ;;
  esac
done

STATE_FILE="$HOME/.dotfiles/install.conf"

# Only used as a hint: we still ask on every run
LAST_CHOICE=""
if [[ -f "$STATE_FILE" ]]; then
  LAST_CHOICE=$(sed -n 's/^bootstrap=\([yn]\)/\1/p' "$STATE_FILE" | head -1)
fi

# Ask every time unless -y / --no-bootstrap was given
if [[ -z "$BOOTSTRAP_CHOICE" ]]; then
  source installers/noninteractive.sh
  DOTFILES_ASSUME_YES=0
  PROMPT="Запустить ./scripts/bootstrap.sh --install (zsh, bat, tmux, neovim, uv, prep)?"
  if [[ -n "$LAST_CHOICE" ]]; then
    PROMPT+=" (в прошлый раз: ${LAST_CHOICE})"
  fi
  if ask_yes "$PROMPT" "${LAST_CHOICE:-y}"; then
    BOOTSTRAP_CHOICE=y
  else
    BOOTSTRAP_CHOICE=n
  fi
fi

# Consent given -> every nested installer runs non-interactively
export DOTFILES_ASSUME_YES=1
export HOMEBREW_NO_ASK=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export DEBIAN_FRONTEND=noninteractive

mkdir -p "$HOME/.dotfiles"
{
  echo "# Последнее решение пользователя (используется только как подсказка при следующем запуске)"
  echo "bootstrap=$BOOTSTRAP_CHOICE"
  echo "ran_at=$(date -Iseconds)"
} > "$STATE_FILE"

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
  installers/noninteractive.sh
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

if [[ "$BOOTSTRAP_CHOICE" == "y" ]]; then
  ./scripts/bootstrap.sh --install --yes || echo "⚠️ bootstrap завершился с ошибкой"
fi

echo "✅ Готово. Перезагрузите shell:  reload-zsh"
echo "   Проверка:  prep --help"

exit 0
