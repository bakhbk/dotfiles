#!/bin/zsh

set +m  # Disable job control messages

SCRIPT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
source "$SCRIPT_DIR/shared/scripts/setup/common.sh"

FVM_VERSION=${1:-"3.38.9"}

printhead "Настраиваем асинхронно Flutter [fvm version $FVM_VERSION] проекты..."

for dir in $(ls -d */ | while read d; do [ -f "$d/.fvmrc" ] && echo "$d"; done); do
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
