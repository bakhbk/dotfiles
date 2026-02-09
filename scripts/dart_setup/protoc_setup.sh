#!/bin/zsh

SCRIPT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
# source "$SCRIPT_DIR/common.sh"  # already sourced

echo "Устанавливаем protoc-gen-dart..."
fvm dart pub global activate protoc_plugin 22.5.0
echo "✅ protoc-gen-dart установлен"