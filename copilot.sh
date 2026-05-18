#!/usr/bin/env bash
set -euo pipefail

# Source shared utilities (INI parser, fzf helper, JSON escaping)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$HOME/own_projects/agent-launcher"

if [[ -f "$PROJECT_DIR/src/shared.sh" ]]; then
  source "$PROJECT_DIR/src/shared.sh"
else
  # Fallback: inline config path for standalone use
  DISPATCH_CONFIG_DIR="${DISPATCH_CONFIG_DIR:-$HOME/.config/dispatch}"
  DISPATCH_CONFIG_FILE="${DISPATCH_CONFIG_DIR}/providers.conf"
  mkdir -p "$DISPATCH_CONFIG_DIR"
  [[ -f "$DISPATCH_CONFIG_FILE" ]] || touch "$DISPATCH_CONFIG_FILE"

  get_provider_names() {
    grep '^\[' "$DISPATCH_CONFIG_FILE" 2>/dev/null | sed 's/\[//;s/\]//' || true
  }
  get_provider_url()       { awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^url=/{sub(/^url=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  get_provider_key()       { awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^key=/{sub(/^key=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  get_provider_last_model(){ awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^last_model=/{sub(/^last_model=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  save_provider() { true; }  # not used in copilot.sh flow
fi

# Alias for copilot.sh legacy
CONFIG_DIR="$DISPATCH_CONFIG_DIR"
CONFIG_FILE="$DISPATCH_CONFIG_FILE"

# --- Parse flags ---
CONTINUE=0
while getopts "c" opt; do
  case $opt in
    c) CONTINUE=1 ;;
    *) ;;
  esac
done
shift $((OPTIND - 1))

# --- Continue mode: use last saved config ---
if [[ "$CONTINUE" -eq 1 ]]; then
  if [[ ! -f "$CONFIG_FILE" ]] || [[ -z "$(get_provider_names)" ]]; then
    echo "No providers configured. Run without -c first."
    exit 1
  fi
  NAMES=$(get_provider_names)
  NAME=$(echo "$NAMES" | fzf --preview 'echo {}')
  [[ -z "$NAME" ]] && echo "Aborted." && exit 1
  BASE_URL=$(get_provider_url "$NAME")
  API_KEY=$(get_provider_key "$NAME")
  MODEL=$(get_provider_last_model "$NAME")
  if [[ -z "$BASE_URL" || -z "$MODEL" ]]; then
    echo "Incomplete config for provider '$NAME'. Run without -c to reconfigure."
    exit 1
  fi
  exec env \
    COPILOT_PROVIDER_BASE_URL="$BASE_URL" \
    COPILOT_PROVIDER_API_KEY="$API_KEY" \
    COPILOT_MODEL="$MODEL" \
    copilot --continue
fi

# --- 1. Choose or add a provider ---
if [[ ! -f "$CONFIG_FILE" ]]; then
  touch "$CONFIG_FILE"
fi

NAMES=$(get_provider_names)
CHOICES=""
if [[ -n "$NAMES" ]]; then
  CHOICES="$NAMES"
fi
CHOICES="${CHOICES}
➕ New provider"

PICKED=$(echo "$CHOICES" | fzf --preview 'echo {}')
[[ -z "$PICKED" ]] && echo "Aborted." && exit 1

if [[ "$PICKED" == "➕ New provider" ]]; then
  # --- Collect new provider ---
  read -rp "Provider name: " NAME
  [[ -z "$NAME" ]] && NAME="default"

  read -rp "Provider Base URL: " BASE_URL
  [[ -z "$BASE_URL" ]] && echo "Base URL is required." && exit 1

  read -rsp "API Key (optional): " API_KEY
  echo
else
  NAME="$PICKED"
  BASE_URL=$(get_provider_url "$NAME")
  API_KEY=$(get_provider_key "$NAME")
fi

# --- 2. Fetch models ---
echo "Fetching models..."
if [[ -n "$API_KEY" ]]; then
  MODELS=$(curl -s -H "Authorization: Bearer $API_KEY" "${BASE_URL}/models" \
    | jq -r '.data[].id // empty' 2>/dev/null)
else
  MODELS=$(curl -s "${BASE_URL}/models" \
    | jq -r '.data[].id // empty' 2>/dev/null)
fi

if [[ -z "$MODELS" ]]; then
  echo "No models found. Check URL and API key."
  exit 1
fi

# --- 3. Pick model via fzf ---
MODEL=$(echo "$MODELS" | fzf --preview 'echo {}')
[[ -z "$MODEL" ]] && echo "No model selected." && exit 1

# --- 4. Save provider config ---
save_provider "$NAME" "$BASE_URL" "$API_KEY" "$MODEL"
echo "Saved: provider=$NAME model=$MODEL"

# --- 5. Launch copilot ---
exec env \
  COPILOT_PROVIDER_BASE_URL="$BASE_URL" \
  COPILOT_PROVIDER_API_KEY="$API_KEY" \
  COPILOT_MODEL="$MODEL" \
  copilot
