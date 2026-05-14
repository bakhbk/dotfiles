#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.config/copilot-run"
CONFIG_FILE="$CONFIG_DIR/providers.conf"

mkdir -p "$CONFIG_DIR"

# --- INI-style helpers ---
get_provider_names() {
  grep '^\[' "$CONFIG_FILE" 2>/dev/null | sed 's/\[//;s/\]//' || true
}

get_provider_url() {
  local name="$1"
  awk -v name="[${name}]" '
    $0 == name { found=1; next }
    /^\[/ { found=0 }
    found && /^url=/ { sub(/^url=/, ""); print }
  ' "$CONFIG_FILE"
}

get_provider_key() {
  local name="$1"
  awk -v name="[${name}]" '
    $0 == name { found=1; next }
    /^\[/ { found=0 }
    found && /^key=/ { sub(/^key=/, ""); print }
  ' "$CONFIG_FILE"
}

get_provider_last_model() {
  local name="$1"
  awk -v name="[${name}]" '
    $0 == name { found=1; next }
    /^\[/ { found=0 }
    found && /^last_model=/ { sub(/^last_model=/, ""); print }
  ' "$CONFIG_FILE"
}

save_provider() {
  local name="$1" url="$2" key="$3" model="$4"
  # Remove existing section if present
  if grep -q "^\[${name}\]" "$CONFIG_FILE" 2>/dev/null; then
    local tmp
    tmp=$(awk -v name="[${name}]" '
      $0 == name { skip=1; next }
      /^\[/ { skip=0 }
      !skip { print }
    ' "$CONFIG_FILE")
    printf '%s\n' "$tmp" > "$CONFIG_FILE"
  fi
  cat >> "$CONFIG_FILE" <<EOF

[${name}]
url=${url}
key=${key}
last_model=${model}
EOF
}

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
LAST_MODEL=$(get_provider_last_model "$NAME")
if [[ -n "$LAST_MODEL" ]]; then
  MODEL=$(echo "$MODELS" | fzf --preview 'echo {}' --query "$LAST_MODEL")
else
  MODEL=$(echo "$MODELS" | fzf --preview 'echo {}')
fi
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
