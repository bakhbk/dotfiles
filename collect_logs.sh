#!/usr/bin/env bash
set -euo pipefail

# Collect Docker container logs into a single file, excluding INFO lines.
OUT=${1:-${OUTPUT_FILE-}}
if [ -z "${OUT}" ]; then
    cat >&2 <<'USAGE'
Usage: collect_logs.sh OUTPUT_FILE
Or set OUTPUT_FILE environment variable.
USAGE
    exit 1
fi

mkdir -p "$(dirname "$OUT")" >/dev/null 2>&1
: > "$OUT"
for c in $(docker ps --format '{{.Names}}'); do
    printf '=== Logs for container: %s ===\n\n' "$c" >>"$OUT"
    docker logs "$c" 2>&1 | grep -v INFO >>"$OUT" || true
    printf '\n----------------------------------------\n\n' >>"$OUT"
done

printf 'Logs collected in %s\n' "$OUT"