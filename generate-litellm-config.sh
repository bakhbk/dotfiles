#!/usr/bin/env bash
set -euo pipefail

# Generate litellm config.yaml from providers.conf
# For each provider: fetches /models endpoint, generates one entry per model
# Reads:  $HOME/.config/dispatch/providers.conf (INI-style)
# Writes: ~/.litellm-config.yaml

CONFIG_FILE="${DISPATCH_CONFIG_FILE:-$HOME/.config/dispatch/providers.conf}"
OUTPUT="${HOME}/.litellm-config.yaml"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "❌ providers.conf not found at $CONFIG_FILE"
  exit 1
fi

# Step 1: Parse providers.conf into a simple TSV: name \t url \t key
PROVIDERS_TSV=$(mktemp)

awk '
/^[[:space:]]*$/ || /^[[:space:]]*#/ { next }
/^\[/ {
  s = $0
  sub(/^[[:space:]]*\[/, "", s)
  sub(/\][[:space:]]*$/, "", s)
  if (s != "") {
    n++
    names[n] = s
    urls[s] = ""
    keys[s] = ""
    current = s
  }
  next
}
current != "" && /=/ {
  idx = index($0, "=")
  key = substr($0, 1, idx - 1)
  val = substr($0, idx + 1)
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
  if (key == "url")        urls[current] = val
  else if (key == "key")   keys[current] = val
}
END {
  for (i = 1; i <= n; i++) {
    print names[i] "\t" urls[names[i]] "\t" keys[names[i]]
  }
}
' "$CONFIG_FILE" > "$PROVIDERS_TSV"

# Step 2: For each provider, fetch models and generate YAML
echo "model_list:" > "$OUTPUT"

while IFS=$'\t' read -r name url key; do
  [[ -z "$url" ]] && continue

  echo "🔍 Fetching models from $name ($url)..."

  # Determine prefix
  if [[ "$url" == *":11434"* ]]; then
    prefix="ollama"
  else
    prefix="openai"
  fi

  # Fetch models from API
  if [[ "$prefix" == "ollama" ]]; then
    # Ollama: use 'ollama list' instead of /models endpoint
    if command -v ollama >/dev/null 2>&1; then
      raw_models=$(ollama list 2>/dev/null | awk 'NR>1 && NF>=3 {print $1}' || true)
      if [[ -z "$raw_models" ]]; then
        echo "⚠️  ollama list returned nothing — using section name as fallback"
        raw_models="$name"
      fi
    else
      echo "⚠️  ollama CLI not found — using section name as fallback"
      raw_models="$name"
    fi
  else
    # OpenAI-compatible: use /models endpoint
    if [[ -n "$key" && "$key" != "none" ]]; then
      raw_models=$(curl -s --max-time 10 -H "Authorization: Bearer $key" "${url}/models" 2>/dev/null | \
        jq -r '.data[].id // empty' 2>/dev/null || true)
    else
      raw_models=$(curl -s --max-time 10 "${url}/models" 2>/dev/null | \
        jq -r '.data[].id // empty' 2>/dev/null || true)
    fi

    # If /models failed or returned nothing, fallback to section name
    if [[ -z "$raw_models" ]]; then
      echo "⚠️  /models returned nothing for $name — using section name as fallback"
      raw_models="$name"
    fi
  fi

  # api_key value
  ak="\"not-needed\""
  if [[ "$key" != "none" && -n "$key" ]]; then
    ak="\"$key\""
  fi

  # Generate entries for each model — each gets its own model_name
  while IFS= read -r model_id; do
    [[ -z "$model_id" ]] && continue

    # Sanitize model_name: use the actual model_id as the name
    ym="$(echo "$model_id" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9.-_' '-')"
    while [[ "$ym" == *"--"* ]]; do ym="${ym/--/-}"; done
    ym="${ym#-}"
    ym="${ym%-}"

    cat >> "$OUTPUT" <<EOF
  - model_name: ${ym}
    litellm_params:
      model: ${prefix}/${model_id}
      api_base: ${url}
      api_key: ${ak}

EOF
  done <<< "$raw_models"
done < "$PROVIDERS_TSV"

rm -f "$PROVIDERS_TSV"

echo ""
echo "✅ Generated $OUTPUT ($(wc -l < "$OUTPUT") lines)"
echo "Run: litellm --config $OUTPUT"
