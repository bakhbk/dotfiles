#!/usr/bin/env bash
set -euo pipefail
trap 'echo "❌ Error on line $LINENO (exit code $?)" >&2' ERR

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
  get_provider_url() { awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^url=/{sub(/^url=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  get_provider_key() { awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^key=/{sub(/^key=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  get_provider_last_model() { awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^last_model=/{sub(/^last_model=/,"" );print}' "$DISPATCH_CONFIG_FILE"; }
  save_provider() {
    local name="$1" url="$2" key="$3" model="$4"
    if grep -q "^\[${name}\]" "$DISPATCH_CONFIG_FILE" 2>/dev/null; then
      local tmp
      tmp=$(awk -v section="[${name}]" '
        $0 == section { skip=1; next }
        /^\[/ { skip=0 }
        !skip { print }
      ' "$DISPATCH_CONFIG_FILE")
      printf '%s\n' "$tmp" > "$DISPATCH_CONFIG_FILE"
    fi
    cat >> "$DISPATCH_CONFIG_FILE" <<EOF

[${name}]
url=${url}
key=${key}
last_model=${model}
EOF
  }
fi

# Alias for copilot.sh legacy
CONFIG_DIR="$DISPATCH_CONFIG_DIR"
CONFIG_FILE="$DISPATCH_CONFIG_FILE"

# --- Parse flags ---
CONTINUE=0
NO_EDIT=0
FULL_DIFF=0
VERBOSE=0
while getopts "cnvf" opt; do
  case $opt in
  c) CONTINUE=1 ;;
  f) FULL_DIFF=1 ;;
  n) NO_EDIT=1 ;;
  v) VERBOSE=1 ;;
  *) ;;
  esac
done
shift $((OPTIND - 1))
[[ "$VERBOSE" -eq 1 ]] && set -x

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
  MODELS=$(curl -s --connect-timeout 10 --max-time 30 -H "Authorization: Bearer $API_KEY" "${BASE_URL}/models" |
    jq -r '.data[].id // empty' 2>/dev/null)
else
  MODELS=$(curl -s --connect-timeout 10 --max-time 30 "${BASE_URL}/models" |
    jq -r '.data[].id // empty' 2>/dev/null)
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

# --- 5. Choose action: copilot or commit-ai ---
echo ""
ACTIONS="copilot
commit-ai"
ACTION=$(echo "$ACTIONS" | fzf --preview 'echo {}')
[[ -z "$ACTION" ]] && echo "Aborted." && exit 1

if [[ "$ACTION" == "copilot" ]]; then
  exec env \
    COPILOT_PROVIDER_BASE_URL="$BASE_URL" \
    COPILOT_PROVIDER_API_KEY="$API_KEY" \
    COPILOT_MODEL="$MODEL" \
    copilot
elif [[ "$ACTION" == "commit-ai" ]]; then
  # --- commit-ai: generate commit message via LLM ---
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
  fi

  if git diff --cached --quiet; then
    echo "❌ No staged changes to commit"
    exit 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "❌ curl is required"
    exit 1
  fi

  if ! command -v jq >/dev/null 2>&1; then
    echo "❌ jq is required"
    exit 1
  fi

  # --- Generate diff (smart mode by default, full via -f) ---
  if [[ "$FULL_DIFF" -eq 1 ]]; then
    # Old behaviour: full staged diff (slow for large repos)
    DIFF="$(git diff --staged)"
  else
    # Smart mode: pick top changed files, send compact diffs with ±3 lines context
    DIFF="$(
      git diff --name-only --staged 2>/dev/null | while IFS= read -r f; do
        case "$f" in
          *.lock|*.sum) continue ;;
          README*|.gitignore|LICENSE*) continue ;;
        esac
        case "$f" in
          *.png|*.jpg|*.gif|*.ico|*.pdf) continue ;;
        esac
        echo "$f"
      done | while IFS= read -r f; do
        cnt=$(git diff --staged "$f" 2>/dev/null | grep '^[-+]' | grep -cv '^[+-]\{3\}' || echo 0)
        printf '%s:%s\n' "$cnt" "$f"
      done | sort -t: -k1nr | head -n 10 | cut -d: -f2- | while IFS= read -r f; do
        echo "--- $f ---"
        git diff --staged -U3 "$f" 2>/dev/null | head -n 60
      done
    )"
  fi

  if [[ "$FULL_DIFF" -eq 1 ]]; then
    echo "🔍 Full diff mode ($(( $(wc -l <<< "$DIFF") )) lines)"
  else
    local_file_count=$(git diff --name-only --staged 2>/dev/null | wc -l)
    echo "🔍 Smart mode: $(( $(echo "$DIFF" | grep '^---' | wc -l) )) source files ($local_file_count total changed, ~10 most modified selected)"
  fi


  # --- Build JSON payload for LLM ---
  payload=$(jq -n --arg diff "$DIFF" --arg model "$MODEL" '{
    model: $model,
    messages: [
      {role: "system", content: "Output ONLY a git commit message. First line MUST start with one of these exact words: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert. Then a colon and space, then the description. Example: feat(auth): add login page\n\nDo NOT output any other text before or after the commit message. No greetings, no explanations, no conversational phrases like I will, Let me, Here is."},
      {role: "user", content: ("Generate a commit message for this diff:\n\n" + $diff)}
    ],
    max_tokens: 1000,
    temperature: 0.2
  }')

  echo "🌐 Calling API: ${BASE_URL}/chat/completions"
  if [[ -n "$API_KEY" ]]; then
    response=$(curl -fsS --connect-timeout 10 --max-time 120 -w "\n%{http_code}" -H "Content-Type: application/json" -H "Authorization: Bearer ${API_KEY}" -d "$payload" "${BASE_URL}/chat/completions" 2>&1 || true)
  else
    response=$(curl -fsS --connect-timeout 10 --max-time 120 -w "\n%{http_code}" -H "Content-Type: application/json" -d "$payload" "${BASE_URL}/chat/completions" 2>&1 || true)
  fi

  http_code=$(echo "$response" | tail -1)
  if [[ "$http_code" != "200" ]]; then
    echo "❌ API returned HTTP $http_code"
    echo "$response" | head -20
    exit 1
  fi

  response=$(echo "$response" | sed '$d')

  if [[ -z "$response" ]] || ! printf '%s' "$response" | jq -e '.choices' >/dev/null 2>&1; then
    echo "❌ API request failed: invalid JSON response"
    echo "$response" | head -20
    exit 1
  fi

  message=$(printf '%s' "$response" | jq -r '
    def fallback_message:
      (.choices[0].message.reasoning_content // "" | split("\n")
        | map(select(length > 0 and
          (contains("feat") or contains("fix") or contains("docs") or contains("style") or contains("refactor") or contains("perf") or contains("test") or contains("build") or contains("ci") or contains("chore") or contains("revert")) ))
        | last // "");

    if (.choices[0].message.content // "" | tostring | gsub("^\\s+|\\s+$"; "")) != "" then
      (.choices[0].message.content | gsub("`"; "") )
    else
      (fallback_message | gsub("`"; "") | gsub("Draft: "; ""))
    end
  ' 2>&1) || { echo "❌ jq parsing failed"; echo "$response" | head -20; exit 1; }

  message="$(printf '%s' "$message" | sed -e '/./,$!d')"

  if [[ -z "$message" ]]; then
    echo "❌ Failed to generate commit message"
    exit 1
  fi

  # Add signoff for preview
  name=$(git config user.name || true)
  email=$(git config user.email || true)
  if [ -n "$name" ] && [ -n "$email" ]; then
    message="$message"$'\n\n'"Signed-off-by: $name <$email>"
  fi

  # No-edit mode: commit directly
  if [[ "$NO_EDIT" -eq 1 ]]; then
    git commit -m "$message"
    echo "✅ Commit created!"
    exit 0
  fi

  # Open in editor for review/edit (empty = cancel)
  tmpmsg=$(mktemp)
  printf '%s\n' "$message" > "$tmpmsg"
  trap 'rm -f "$tmpmsg"' EXIT

  echo "📝 Opening editor (save+quit to commit, empty file to cancel)..."

  try_editor() {
    local editors="${EDITOR:-nvim} vim vi nano"
    for e in $editors; do
      if command -v "$e" &>/dev/null; then
        echo "✏️  Using editor: $e"
        local ret=0
        "$e" "$tmpmsg" || ret=$?
        if [[ $ret -ne 0 ]]; then
          echo "⚠️  Editor '$e' exited with code $ret"
        fi
        return $ret
      fi
    done
    echo "No editor found. Use this message? [Y/n]"
    read -r ans
    [[ "$ans" =~ ^[Nn]$ ]] && echo "Canceled" && exit 1
    git commit -m "$(cat "$tmpmsg")"
  }

  try_editor || true

  edited=$(cat "$tmpmsg")
  if [[ -z "$(printf '%s' "$edited" | tr -d '[:space:]')" ]]; then
    echo "❌ Commit canceled (message empty)"
  else
    git commit -m "$edited"
    echo "✅ Commit created!"
  fi
fi
