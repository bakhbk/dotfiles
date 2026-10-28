#!/usr/bin/env bash

# Install `uv` (Astral) if it is missing.
# Works on macOS (Homebrew) and Linux (official installer, no sudo needed).

set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "✅ uv уже установлен: $(command -v uv)"
  exit 0
fi

echo "📦 Устанавливаем uv..."

# 1. Homebrew (macOS / Linuxbrew)
if command -v brew >/dev/null 2>&1; then
  brew install uv
fi

# 2. Official installer (installs into ~/.local/bin)
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# 3. Last resort: pip
if ! command -v uv >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "❌ uv не удалось установить. Установите вручную: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

# Make sure ~/.local/bin is on PATH for the current session and future shells
mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
echo "✅ uv установлен: $(command -v uv)"
