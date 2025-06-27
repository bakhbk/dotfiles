#!/bin/bash

_gbci() {
  if ! command -v fzf &>/dev/null; then
    echo "fzf не установлен. Пожалуйста, установите fzf перед использованием этого скрипта."
    return 1
  fi

  # Improved branch listing:  Show only actual branch names.
  branches=$(git branch -a | grep -v '\*' | grep -v 'HEAD ->') # <- Key change

  selected_branch=$(echo "$branches" | fzf --prompt="Выберите ветку: " --height=40% --reverse)

  if [ -z "$selected_branch" ]; then
    echo "Выбор ветки отменен."
    return 1
  fi

  # Extract branch name (more robust):
  branch_name=$(echo "$selected_branch" | sed 's/^\* //;s/remotes\/[^\/]*\///' | xargs)

  # Check if it's a remote branch and handle accordingly:
  if [[ "$selected_branch" == remotes/* ]]; then                            # <- Check for remote branch
    local_branch_name=$(echo "$branch_name" | sed 's/remotes\/[^\/]*\///')  # Extract local name
    if [[ $(git show-ref --verify "refs/heads/$local_branch_name") ]]; then # Check if local branch exists
      git checkout "$local_branch_name"                                     # Switch if exists
    else
      git checkout -b "$local_branch_name" "origin/$local_branch_name" # Create and switch if not
    fi
  else
    git checkout "$branch_name" # Checkout local branch
  fi

  echo "Вы переключились на ветку: $branch_name"
  return 0
}

# Example usage (add to .bashrc or .zshrc):
alias gbci='_gbci'
