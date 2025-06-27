#!/usr/bin/env bash

if ! command -v fzf >/dev/null; then
  git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
  ~/.fzf/install --key-bindings --completion --update-rc
  source <(fzf --zsh)
fi
