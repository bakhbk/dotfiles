#!/bin/zsh

set +m  # Disable job control messages

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]:-$0}")"
source "$SCRIPT_DIR/common.sh"

# Определяем Flutter версию
if [ -n "$1" ]; then
  FVM_VERSION="$1"
else
  FVM_VERSION=$(get_latest_stable_fvm)
fi

printhead "Настраиваем асинхронно Flutter [fvm version $FVM_VERSION] проекты..."

shopt -s nullglob 2>/dev/null || true
for dir in */; do
  [ -f "$dir/.fvmrc" ] || continue
  (
    echo "ℹ️ Настраиваем Flutter проект в $dir ..."
    cd "$dir" || exit
    fvm use --force -s "$FVM_VERSION" >/dev/null 2>&1
    fvm dart --disable-analytics >/dev/null 2>&1
    fvm flutter --disable-analytics >/dev/null 2>&1
    fvm flutter clean >/dev/null 2>&1
    fvm dart pub get >/dev/null 2>&1
    cd - || exit
  ) &
done
wait
