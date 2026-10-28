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

# Same, but pretend uv is not installed anywhere (no ~/.local/bin on PATH)
run_install_without_uv() {
  env PATH=/usr/bin:/bin HOME="$1" bash "$REPO/install.sh" "${@:2}" </dev/null >/tmp/install-test.log 2>&1
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

# 4. the decision is logged, but re-asked on the next run
check "install.conf written" "grep -q '^bootstrap=y' $H1/.dotfiles/install.conf"
run_install "$H1"
check "second run asks again" "grep -q 'Запустить ./scripts/bootstrap.sh' /tmp/install-test.log"
check "previous choice shown as default" "grep -q 'в прошлый раз: y' /tmp/install-test.log"

# 5. --no-bootstrap remembers n and is asked with n as default
H2=$(mktemp -d)
run_install "$H2" --no-bootstrap
check "bootstrap=n stored" "grep -q '^bootstrap=n' $H2/.dotfiles/install.conf"
run_install "$H2"
check "default flips to n after a refusal" "grep -q 'в прошлый раз: n' /tmp/install-test.log"

# 6. -y never asks
run_install "$H2" -y
check "-y runs without any question" "! grep -q 'ask_yes' /tmp/install-test.log"

# 7. configs are copied regardless of arguments
check "zsh_aliases copied" "grep -q 'alias prep-fast' $H2/.dotfiles/zsh_aliases"
check "prep has python3 fallback (zsh)" "grep -q 'python3' $H2/.dotfiles/zsh_aliases"
check "prep has python3 fallback (wrapper)" "grep -q 'python3' $H2/.local/bin/prep"
check "doctor.sh is executable" "[ -x $REPO/installers/doctor.sh ]"

# 8. declining the bootstrap must NOT pull uv (no brew, no 500MB of llvm/rust)
H3=$(mktemp -d)
mkdir -p "$H3/.dotfiles"
printf 'bootstrap=n\n' > "$H3/.dotfiles/install.conf"
run_install_without_uv "$H3"
check "uv skipped when bootstrap=n" "grep -q 'uv не устанавливаем' /tmp/install-test.log"
check "no uv download attempted" "! grep -q 'Устанавливаем uv' /tmp/install-test.log"
check "prep still runs via python3" "env PATH=/usr/bin:/bin DOTFILES_DIR=$REPO $H3/.local/bin/prep --help >/dev/null 2>&1"

# 9. --uv forces it even without bootstrap
run_install_without_uv "$H3" --uv
check "--uv overrides the refusal" "grep -q 'Устанавливаем uv' /tmp/install-test.log"

echo
echo "Passed: $PASS, Failed: $FAIL"
[[ $FAIL -eq 0 ]]
