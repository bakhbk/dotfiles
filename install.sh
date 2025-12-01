#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.

set -euxo pipefail

CONFIGS=(
  .zsh_aliases
  .zsh_tools
  .zshenv
  .zshrc
  .install-oh-my-zsh.sh
  .shell_prompt
  .git_checkout_branch.sh
  .git_delete_branch.sh
  .tmux_session_selector.sh
  .nvmv.sh
  .minimal.zshrc
  .create_tmux_session.sh
  .commit.sh
  .fvm_tools.sh
  .ollama_fzf.sh
)

# Configs that should be copied to the home directory.
CONFIGS_HOME_DIR=(
  .tmux.conf
  .zshrc
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

./.install-oh-my-zsh.sh
./.install_fzf.sh

exit 0
