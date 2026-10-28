#!/usr/bin/env bash
# Non-interactive: пользователь уже согласился на установку (см. install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive
# Install/pin a Zulu JDK and export JAVA_HOME in ~/.zshrc.
# Usage: install_java_sdk.sh [version] [--force] [--check]   (default version: 17)
#   --force  reinstall the cask even if the JDK is already present
#   --check  only report the detected JDK home (no install, no writes); exit 0/1
set -euo pipefail

ZSHRC="${ZSHRC:-$HOME/.zshrc}"
version=17 force=0 check=0

for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    --check) check=1 ;;
    [0-9]*)  version="$arg" ;;
    *) echo "Usage: $0 [version] [--force] [--check]"; exit 1 ;;
  esac
done

works() { [[ -n "${1:-}" && -x "$1/bin/java" ]] && "$1/bin/java" -version 2>&1 | head -1 | grep -q "version \"$version"; }

find_home() {
  home="$(/usr/libexec/java_home -v "$version" 2>/dev/null || true)"
  works "$home" || home=""
  echo "$home"
}

home="$(find_home)"

if (( check )); then
  echo "${home:-JAVA $version SDK not found}"
  [[ -n "$home" ]] || exit 1
  exit 0
fi

if [[ -z "$home" || $force == 1 ]]; then
  echo "JAVA $version SDK is not installed. Initiating installation..."
  echo "Password may be required to install JAVA $version SDK"
  brew reinstall --cask "zulu@$version" || { echo "Failed to install JAVA $version SDK"; exit 1; }
  home="$(find_home)"
fi

if ! works "$home"; then
  echo "ERROR: JAVA $version SDK not found. Install it with: brew install --cask zulu@$version"
  exit 1
fi

echo "JAVA $version SDK found: $home"
"$home/bin/java" -version 2>&1 | head -1

sed -i '' "s|^export JAVA_HOME=.*|export JAVA_HOME=$home|" "$ZSHRC"
grep -q '^export JAVA_HOME=' "$ZSHRC" ||
  printf '\nexport JAVA_HOME=%s\nexport PATH="$JAVA_HOME/bin:$PATH"\n' "$home" >> "$ZSHRC"

echo "JAVA_HOME updated in $ZSHRC - restart your IDE/shell to apply"
