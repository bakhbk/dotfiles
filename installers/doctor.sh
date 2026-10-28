#!/usr/bin/env bash

# Diagnostic for the `prep` command: what is missing and how to fix it.
#   ./installers/doctor.sh

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOTFILES_DIR="${DOTFILES_DIR:-$REPO_DIR}"
SCRIPT="$DOTFILES_DIR/scripts/prep-agents/prep-agents.py"
PROBLEMS=0

report_ok()  { echo "✅ $1"; }
report_bad() { echo "❌ $1"; echo "   → $2"; PROBLEMS=$((PROBLEMS + 1)); }

[[ -d "$DOTFILES_DIR" ]] && report_ok "репозиторий dotfiles: $DOTFILES_DIR" || report_bad "репозиторий не найден" "cd $DOTFILES_DIR && git pull && ./install.sh -y"
[[ -f "$SCRIPT" ]] && report_ok "prep-agents.py существует" || report_bad "нет $SCRIPT" "git pull в ~/dotfiles, затем ./install.sh -y"

if command -v uv >/dev/null 2>&1; then
  report_ok "uv: $(command -v uv) ($(uv --version 2>/dev/null))"
elif command -v python3 >/dev/null 2>&1; then
  report_ok "uv нет, но есть python3 — prep работает в fallback-режиме"
else
  report_bad "нет ни uv, ни python3" "brew install uv  (или: curl -LsSf https://astral.sh/uv/install.sh | sh)"
fi

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  report_bad "~/.local/bin не в PATH" "добавьте в ~/.zshrc: export PATH=\"$HOME/.local/bin:$PATH\""
else
  report_ok "~/.local/bin в PATH"
fi

if [[ -f "$HOME/.dotfiles/dotfiles.env" ]]; then
  report_ok "DOTFILES_DIR записан: $(cat "$HOME/.dotfiles/dotfiles.env" | tail -1)"
else
  report_bad "нет ~/.dotfiles/dotfiles.env" "./install.sh -y"
fi

if [[ -f "$HOME/.config/dispatch/providers.conf" ]]; then
  report_ok "providers.conf найден"
else
  report_bad "нет ~/.config/dispatch/providers.conf" "create it — prep reads providers from there (see scripts/prep-agents/README.md)"
fi

if command -v prep >/dev/null 2>&1; then
  if prep --help >/dev/null 2>&1; then
    report_ok "prep запускается"
  else
    report_bad "prep есть, но падает" "prep --help — смотрите вывод выше"
  fi
else
  report_bad "команда prep не найдена" "./installers/install_prep.sh"
fi

echo
if [[ $PROBLEMS -eq 0 ]]; then
  echo "✅ Всё в порядке."
else
  echo "⚠️  Проблем: $PROBLEMS"
  exit 1
fi
