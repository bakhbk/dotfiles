#!/usr/bin/env bash

# Shared non-interactive switches for all installers in this repo.
# Source it at the top of a script:  source "$(dirname "${BASH_SOURCE[0]}")/noninteractive.sh"
#
# DOTFILES_ASSUME_YES=1  -> пользователь уже согласился на установку, вопросов нет
# HOMEBREW_NO_ASK=1      -> отключает "Do you want to proceed with the installation? [y/n]"
# DEBIAN_FRONTEND        -> apt не спрашивает про конфигурацию пакетов

export DOTFILES_ASSUME_YES="${DOTFILES_ASSUME_YES:-1}"
export HOMEBREW_NO_ASK=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export DEBIAN_FRONTEND=noninteractive

# ask_yes "prompt" [default=y]  -> 0 (yes) / 1 (no)
ask_yes() {
  local prompt="${1:-Продолжить?}" default="${2:-y}" ans
  if [[ "${DOTFILES_ASSUME_YES:-0}" == "1" || "${DOTFILES_ASSUME_YES:-}" == "true" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "⚠️  ${prompt} — нет TTY, автоматически: ${default}"
    [[ "$default" == "y" ]] && return 0
    return 1
  fi
  while true; do
    read -r -p "$prompt [y/n]: " ans || ans="$default"
    case "$ans" in
      y | Y | yes) return 0 ;;
      n | N | no) return 1 ;;
      *) [[ "$default" == "y" ]] && return 0 || return 1 ;;
    esac
  done
}
