#!/usr/bin/env bash
# Self-test for the installer: verifies that after the user consents once,
# nothing in the nested installers asks any questions, and `prep` works.
#
#   ./scripts/tests/test_install.sh

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0

check() {
  local name="$1" cond="$2"
  if eval "$cond"; then
    echo "✅ $name"
    PASS=$((PASS + 1))
  else
    echo "❌ $name"
    FAIL=$((FAIL + 1))
  fi
}

run_install() {
  HOME="$1" bash "$REPO/install.sh" "${@:2}" </dev/null >/tmp/install-test.log 2>&1
  local rc=$?
  echo "exit=$rc" >> /tmp/install-test.log
  return 0
}

# 1. first run with -y
H1=$(mktemp -d)
run_install "$H1" -y
check "install.sh -y exited 0" "grep -q 'exit=0' /tmp/install-test.log"

# 2. prep installed and works
check "prep wrapper exists" "[ -x $H1/.local/bin/prep ]"
check "prep runs" "HOME=$H1 zsh -ic 'prep --help' >/dev/null 2>&1"
check "prep presets exist" "[ -x $H1/.local/bin/prep-fast ] && [ -x $H1/.local/bin/prep-clean ]"
check "uv available" "command -v uv >/dev/null"

# 3. no prompts anywhere in the run
check "no interactive prompt" "! grep -qiE 'Do you want to proceed|read -r -p .*\[y/n\]' /tmp/install-test.log"

# 4. decision is remembered
check "install.conf written" "grep -q '^bootstrap=y' $H1/.dotfiles/install.conf"
run_install "$H1"
check "second run does not ask" "grep -q 'Решение уже сохранено' /tmp/install-test.log"

# 5. --no-bootstrap remembers n
H2=$(mktemp -d)
run_install "$H2" --no-bootstrap
check "bootstrap=n stored" "grep -q '^bootstrap=n' $H2/.dotfiles/install.conf"
run_install "$H2"
check "no prompt when bootstrap=n stored" "! grep -q 'read -r -p' /tmp/install-test.log"

# 6. --ask forces the question
run_install "$H2" --ask
check "--ask shows the question" "grep -q 'Запустить ./scripts/bootstrap.sh' /tmp/install-test.log"

# 7. configs are copied regardless of arguments
check "zsh_aliases copied" "grep -q 'alias prep-fast' $H2/.dotfiles/zsh_aliases"

echo
echo "Passed: $PASS, Failed: $FAIL"
[[ $FAIL -eq 0 ]]
