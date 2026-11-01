#!/bin/bash

choose_tmux_session() {
  session_names=$(tmux ls -F '#S')

  if [[ -z "$session_names" ]]; then
    echo "Нет активных сессий tmux."
    return 1
  fi

  selected_session=$(echo "$session_names" | fzf --height 40% --border --reverse --preview 'tmux capture-pane -p -S -30' --preview-window down:60% +s --tac)

  if [[ -n "$selected_session" ]]; then
    # для `ta` необходим плагин ohmyzsh tmux
    # https://github.com/ohmyzsh/ohmyzsh/tree/master/plugins/tmux
    ta "$selected_session"
    echo "Переключаемся на сессию: $selected_session"
  else
    echo "Сессия не выбрана."
  fi
}

alias tsc='choose_tmux_session'
