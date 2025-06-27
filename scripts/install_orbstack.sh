#!/bin/bash

# Обертка для установки OrbStack
# Использование: ./scripts/install_orbstack.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Запуск установки OrbStack..."
echo "📂 Dotfiles директория: $DOTFILES_DIR"
echo

# Запускаем основной скрипт установки
exec "$DOTFILES_DIR/.install_orbstack.sh"
