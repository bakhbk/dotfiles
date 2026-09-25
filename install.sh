#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.

set -euxo pipefail

# Запуск bootstrap с подтверждением в начале
read -p "Запустить ./scripts/bootstrap.sh --install? [y/N]: " confirm
RUN_BOOTSTRAP=false
if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
  RUN_BOOTSTRAP=true
fi

# Extracted clipboard helper installer
./installers/install_clipboard_helpers.sh || true

CONFIGS=(
  shell/bash_tools
  shell/zsh_aliases
  shell/zsh_tools
  shell/agent-runner.sh
  shell/zshenv
  shell/.zshrc
  shell/project_clean.sh
  installers/install-oh-my-zsh.sh
  shell/shell_prompt
  git/git_checkout_branch.sh
  git/git_delete_branch.sh
  tmux/tmux_session_selector.sh
  shell/nvmv.sh
  shell/minimal.zshrc
  tmux/create_tmux_session.sh
  utils/commit.sh
  utils/fvm_tools.sh
  ollama/ollama_fzf.sh
  utils/clean.sh
)

# Configs that should be copied to the home directory.
CONFIGS_HOME_DIR=(
  tmux/.tmux.conf
  shell/.zshrc
  shell/.bashrc
)

if [ $# -eq 0 ]; then
  for i in "${CONFIGS_HOME_DIR[@]}"; do
    cp -rvf "${i}" ~/
  done
  for i in "${CONFIGS[@]}"; do
    mkdir -p ~/.dotfiles
    cp -rvf "${i}" ~/.dotfiles/
  done

fi

./installers/install-oh-my-zsh.sh
./installers/install_fzf.sh

if $RUN_BOOTSTRAP; then
  ./scripts/bootstrap.sh --install
fi

exit 0
