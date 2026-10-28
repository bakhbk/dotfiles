#!/usr/bin/env bash

# Install fzf non-interactively when the user already consented (see install.sh).

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/noninteractive.sh"

if ! command -v fzf >/dev/null; then
  git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
  if [[ "${DOTFILES_ASSUME_YES:-0}" == "1" ]]; then
    ~/.fzf/install --key-bindings --completion --update-rc < /dev/null
  else
    ~/.fzf/install --key-bindings --completion --update-rc
  fi
  export PATH="$HOME/.fzf/bin:$PATH"
  source <(fzf --zsh)
fi
