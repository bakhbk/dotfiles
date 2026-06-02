#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.

set -euxo pipefail

# Extracted clipboard helper installer
./installers/install_clipboard_helpers.sh || true

CONFIGS=(
  shell/zsh_aliases
  shell/zsh_tools
  shell/zshenv
  shell/.zshrc
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

exit 0
