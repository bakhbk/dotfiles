#!/usr/bin/env bash

# Install `uv` (Astral) if it is missing.
# Order matters: the lightweight official installer first, Homebrew only as a
# last resort — on older macOS `brew install uv` drags in python@3.15, llvm
# and rust (hundreds of MB).
#
#   DOTFILES_INSTALL_UV=0 -> skip entirely (user declined extra packages)

# Non-interactive: the user already consented (see install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive

set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "✅ uv уже установлен: $(command -v uv)"
  exit 0
fi

if [[ "${DOTFILES_INSTALL_UV:-1}" != "1" ]]; then
  echo "ℹ️  uv не устанавливаем (отказ от доп. пакетов). prep будет работать через python3."
  echo "    Принудительно: DOTFILES_INSTALL_UV=1 ./installers/install_uv.sh"
  exit 0
fi

# 1. Official astral installer (≈15 MB, no system deps) -> ~/.local/bin
echo "📦 Устанавливаем uv (официальный installer → ~/.local/bin)..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. pip fallback
if ! command -v uv >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user uv || true
  export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Homebrew last resort (brew can be locked by a parallel install)
if ! command -v uv >/dev/null 2>&1 && command -v brew >/dev/null 2>&1; then
  for attempt in 1 2 3; do
    if brew install uv; then
      break
    fi
    echo "⚠️  brew install uv не прошёл (попытка $attempt) — ждём 5 c..."
    sleep 5
  done
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "⚠️  uv не установлен — prep будет работать через python3 (fallback)" >&2
  exit 1
fi

echo "✅ uv установлен: $(command -v uv)"
