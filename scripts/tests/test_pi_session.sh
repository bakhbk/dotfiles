#!/usr/bin/env zsh
# TDD harness for shell/pi_session.sh: session-dir resolution + id→path lookup.
#   ./scripts/tests/test_pi_session.sh
# Uses a stub `pi` binary; never calls the real one.

REPO="$(cd "$(dirname "${0:A}")/../.." && pwd)"
SCRIPT="$REPO/shell/pi_session.sh"
PASS=0; FAIL=0

check() {
  local name="$1" cond="$2"
  if eval "$cond"; then echo "✅ $name"; PASS=$((PASS + 1))
  else echo "❌ $name"; FAIL=$((FAIL + 1)); fi
}

T="$(mktemp -d)"
ID_LOCAL="01a196ee-b7c4-7698-9343-b6c54205d8ee"
ID_GLOBAL="01a1a123-3960-730a-9d4c-78c293f50b69"
ID_NOWHERE="00000000-0000-0000-0000-000000000000"
F_LOCAL="$T/base-demo/sessions/--x--/2026-01-01T00-00-00-000Z_${ID_LOCAL}.jsonl"
F_GLOBAL="$T/global/sessions/--y--/2026-01-01T00-00-00-000Z_${ID_GLOBAL}.jsonl"

mkdir -p "$T/base-demo/sessions/--x--" "$T/base-demo/cbc-gbu" "$T/base-demo/wt/cbc-293/tgu_front" "$T/global/sessions/--y--" "$T/bin" "$T/plain" "$T/other"
touch "$F_LOCAL" "$F_GLOBAL"
cat > "$T/bin/pi" <<'EOF'
#!/bin/sh
printf 'DIR=%s\nARGS=%s\n' "${PI_CODING_AGENT_SESSION_DIR:-}" "$*"
EOF
chmod +x "$T/bin/pi"

export PI_GLOBAL_SESSION_DIR="$T/global/sessions"
source "$SCRIPT"
PATH="$T/bin:$PATH"
[[ -x "$T/bin/pi" ]] || { echo "FATAL: stub pi missing"; exit 1 }

check "local dir chosen"     "(cd $T/base-demo/cbc-gbu; pi) | grep -q '^DIR=$T/base-demo/sessions$'"
check "deep worktree cwd"    "(cd $T/base-demo/wt/cbc-293/tgu_front; pi) | grep -q '^DIR=$T/base-demo/sessions$'"
check "no base ancestor"     "(cd $T/plain; pi) | grep -q '^DIR=$'"
check "id found locally"     "(cd $T/base-demo/cbc-gbu; pi --session $ID_LOCAL) | grep -q 'ARGS=--session $F_LOCAL'"
check "id fallback global"   "(cd $T/base-demo/cbc-gbu; pi --session $ID_GLOBAL) | grep -q 'ARGS=--session $F_GLOBAL'"
check "fork id resolves"     "(cd $T/base-demo/cbc-gbu; pi --fork $ID_LOCAL) | grep -q '${ID_LOCAL}.jsonl'"
check "unknown id passthrough" "(cd $T/base-demo/cbc-gbu; pi --session $ID_NOWHERE) | grep -q 'ARGS=--session $ID_NOWHERE'"
check "cli session-dir wins" "(cd $T/base-demo/cbc-gbu; pi --session-dir $T/other) | grep -q 'DIR=$T/other'"
check "flags preserved"      "(cd $T/base-demo/cbc-gbu; pi -nc -np -ns -ne -c) | grep -q 'ARGS=-nc -np -ns -ne -c'"
check "existing path untouched" "(cd $T/base-demo/cbc-gbu; pi --session $F_LOCAL) | grep -q 'ARGS=--session $T/base-demo/sessions'"
check "user env respected"   "(cd $T/plain; PI_GLOBAL_SESSION_DIR=$T/nope PI_CODING_AGENT_SESSION_DIR=$T/global/sessions pi --session $ID_GLOBAL) | grep -q '${ID_GLOBAL}.jsonl'"

rm -rf "$T"
echo "pass=$PASS fail=$FAIL"
(( FAIL == 0 ))
