#!/usr/bin/env bash

if ! command -v fzf >/dev/null; then
  git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
  ~/.fzf/install --key-bindings --completion --update-rc
  export PATH="$HOME/.fzf/bin:$PATH"
  source <(fzf --zsh)
fi
