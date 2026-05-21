#!/usr/bin/env bash

set -eu

# On Linux, ensure a clipboard helper is installed (wl-clipboard, xclip or xsel).
# This makes tmux copy-paste with system clipboard work across Wayland/X11.
if [ "$(uname)" = "Linux" ]; then
  to_install=()
  for cmd in wl-copy xclip xsel; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      case "$cmd" in
        wl-copy) pkg=wl-clipboard ;;
        xclip) pkg=xclip ;;
        xsel) pkg=xsel ;;
      esac
      to_install+=("$pkg")
    fi
  done

  if [ ${#to_install[@]} -gt 0 ]; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y "${to_install[@]}"
    elif command -v dnf >/dev/null 2>&1; then
      sudo dnf install -y "${to_install[@]}"
    elif command -v pacman >/dev/null 2>&1; then
      sudo pacman -Sy --noconfirm "${to_install[@]}"
    elif command -v zypper >/dev/null 2>&1; then
      sudo zypper install -y "${to_install[@]}"
    else
      echo "Please install one of: ${to_install[*]} (no supported package manager detected)"
    fi
  fi
elif [ "$(uname)" = "Darwin" ]; then
  if ! command -v reattach-to-user-namespace >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      brew install reattach-to-user-namespace
    else
      echo "Homebrew required to install reattach-to-user-namespace"
    fi
  fi
fi
