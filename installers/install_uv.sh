#!/usr/bin/env bash
# Non-interactive: пользователь уже согласился на установку (см. install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive

# Install `uv` (Astral) if it is missing.
# Works on macOS (Homebrew) and Linux (official installer, no sudo needed).

set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "✅ uv уже установлен: $(command -v uv)"
  exit 0
fi

echo "📦 Устанавливаем uv..."

echo "📦 Устанавливаем uv..."

# 1. Homebrew (macOS / Linuxbrew). Brew can be locked by a parallel install
#    (rust/llvm/...), so a failure here must NOT abort the script.
if command -v brew >/dev/null 2>&1; then
  for attempt in 1 2 3; do
    if brew install uv; then
      break
    fi
    echo "⚠️  brew install uv не прошёл (попытка $attempt) — жем 5 c..."
    sleep 5
  done
fi

# 2. Official installer (installs into ~/.local/bin)
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# 3. Last resort: pip
if ! command -v uv >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi

# Make sure ~/.local/bin is reachable in this and future sessions
if [[ -d "$HOME/.local/bin" ]] && ! command -v uv >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "⚠️  uv не установлен — prep будет работать через python3 (fallback)" >&2
  exit 1
fi

echo "✅ uv установлен: $(command -v uv)"
