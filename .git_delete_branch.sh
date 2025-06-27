#!/bin/bash

function _delete_branches() {
  if ! command -v fzf &>/dev/null; then
    echo "fzf не установлен. Пожалуйста, установите fzf перед использованием этого скрипта."
    return 1
  fi

  git branch |
    grep --invert-match '\*' |
    cut -c 3- |
    fzf --multi --preview="git log {} --" |
    xargs --no-run-if-empty git branch --delete --force
}

# Example usage (add to .bashrc or .zshrc):
alias gbdi='_delete_branches'
