#!/usr/bin/env bash

# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.

set -euxo pipefail

CONFIGS=(
  .tmux.conf
  .zsh_aliases
  .zsh_tools
  .zshenv
  .zshrc
  .install-oh-my-zsh.sh
  .shell_promt
  .git_checkout_branch.sh
  .git_delete_branch.sh
  .tmux_session_selector.sh
  .nvmv.sh
)

if [ $# -eq 0 ]; then
  for i in "${CONFIGS[@]}"; do
    cp -rvf "${i}" ~/
  done

  exit 0
fi

for i in "${CONFIGS[@]}"; do
  scp -r "${i}" $1:~/
done
