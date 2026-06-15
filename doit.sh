#!/usr/bin/env bash
# doit.sh — Non-interactive-first CLI for AI-powered workflows
# 
# Usage:
#   ./doit.sh                          # Interactive mode (fzf menus)
#   ./doit.sh --provider kr-jarvis     # Skip provider selection
#   ./doit.sh -c                       # Continue with last config
#   ./doit.sh --action commit-ai       # Skip action selection
#   ./doit.sh --no-edit                # Commit without editor (commit-ai)
#   ./doit.sh --dry-run                # Show generated message, don't commit (commit-ai)
#   ./doit.sh --model gpt-4o           # Override model selection
#
# Examples:
#   ./doit.sh --provider kr-jarvis --action commit-ai --no-edit
#   ./doit.sh -c --provider lmstudio --action copilot
#   ./doit.sh --provider kr-jarvis --action commit-ai --dry-run

set -euo pipefail
trap 'echo "❌ Error on line $LINENO (exit code $?)" >&2' ERR

# ============================================================================
# Configuration paths
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$HOME/own_projects/agent-launcher"

# ============================================================================
# Configuration paths
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$HOME/own_projects/agent-launcher"

# Try to source shared utilities (optional — doit.sh works standalone)
if [[ -f "$PROJECT_DIR/src/shared.sh" ]]; then
  source "$PROJECT_DIR/src/shared.sh"
fi

# Try to load config.env if it exists (pre-built ENV vars)
CONFIG_ENV_FILE="${DISPATCH_CONFIG_DIR:-$HOME/.config/dispatch}/config.env"
if [[ -f "$CONFIG_ENV_FILE" ]]; then
  source "$CONFIG_ENV_FILE"
fi

# --- Inline INI parser (fallback if shared.sh not loaded) ---
if ! type get_provider_names &>/dev/null; then
  DISPATCH_CONFIG_DIR="${DISPATCH_CONFIG_DIR:-$HOME/.config/dispatch}"
  DISPATCH_CONFIG_FILE="${DISPATCH_CONFIG_DIR}/providers.conf"
  mkdir -p "$DISPATCH_CONFIG_DIR"
  [[ -f "$DISPATCH_CONFIG_FILE" ]] || touch "$DISPATCH_CONFIG_FILE"

  get_provider_names() {
    grep '^\[' "$DISPATCH_CONFIG_FILE" 2>/dev/null | sed 's/\[//;s/\]//' || true
  }

  get_provider_url() {
    awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^url *=/{sub(/^url *=*/,"");gsub(/^[ \t]+|[ \t]+$/,"",$0);print}' "$DISPATCH_CONFIG_FILE"
  }

  get_provider_key() {
    awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^key *=/{sub(/^key *=*/,"");gsub(/^[ \t]+|[ \t]+$/,"",$0);print}' "$DISPATCH_CONFIG_FILE"
  }

  get_provider_last_model() {
    awk -v s="[${1}]" '$0==s{f=1;next}/^\[/{f=0}f&&/^last_model *=/{sub(/^last_model *=*/,"");gsub(/^[ \t]+|[ \t]+$/,"",$0);print}' "$DISPATCH_CONFIG_FILE"
  }

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

# Legacy alias for compatibility
CONFIG_DIR="${DISPATCH_CONFIG_DIR:-$HOME/.config/dispatch}"
CONFIG_FILE="${DISPATCH_CONFIG_FILE:-$CONFIG_DIR/providers.conf}"

# ============================================================================
# Argument parsing — flags first, then positional args
# ============================================================================
INTERACTIVE=0       # -i: force interactive mode (fzf menus)
CONTINUE=0          # -c: use last saved config
NO_EDIT=0           # --no-edit: skip editor in commit-ai
FULL_DIFF=0         # -f: use full diff (not smart mode) in commit-ai
VERBOSE=0           # -v: enable bash debug mode
DRY_RUN=0           # --dry-run: show generated message, don't commit

PROVIDER=""         # --provider: explicit provider name
ACTION=""           # --action: explicit action (copilot|commit-ai)
MODEL_OVERRIDE=""   # --model: override model selection

while [[ $# -gt 0 ]]; do
  case $1 in
    -i|--interactive)  INTERACTIVE=1; shift ;;
    -c|--continue)     CONTINUE=1; shift ;;
    -f|--full-diff)    FULL_DIFF=1; shift ;;
    -n|--no-edit)      NO_EDIT=1; shift ;;
    -v|--verbose)      VERBOSE=1; shift ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --provider)        PROVIDER="$2"; shift 2 ;;
    --action)          ACTION="$2"; shift 2 ;;
    --model)           MODEL_OVERRIDE="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ "$VERBOSE" -eq 1 ]] && set -x

# ============================================================================
# Helper: show non-interactive usage hint
# ============================================================================
# Use ~/dotfiles/doit.sh for clean, portable hints
SCRIPT_PATH="~/dotfiles/doit.sh"
show_hint() {
  local action="$1" provider="$2" model="$3" extra="${4:-}"
  echo ""
  printf "💡 Non-interactive: %s --provider %s --model %s --action %s" \
    "$SCRIPT_PATH" "$provider" "$model" "$action"
  [[ -n "$extra" ]] && printf " %s" "$extra"
  echo ""
}

# ============================================================================
# Mode: Interactive (-i) — skip all flags, full fzf flow
# ============================================================================
if [[ "$INTERACTIVE" -eq 1 ]]; then
  CONTINUE=0
  PROVIDER=""
  ACTION=""
  MODEL_OVERRIDE=""
fi

# ============================================================================
# Mode: Continue (-c) — use last saved config
# ============================================================================
if [[ "$CONTINUE" -eq 1 ]]; then
  if [[ ! -f "$CONFIG_FILE" ]] || [[ -z "$(get_provider_names)" ]]; then
    echo "No providers configured. Run without -c first." >&2
    exit 1
  fi

  # Select provider: use --provider flag or fzf interactive
  if [[ -z "$PROVIDER" ]]; then
    PROVIDER=$(get_provider_names | fzf --preview 'echo {}')
  fi
  [[ -z "$PROVIDER" ]] && echo "Aborted." >&2 && exit 1

  BASE_URL=$(get_provider_url "$PROVIDER")
  API_KEY=$(get_provider_key "$PROVIDER")
  MODEL="${MODEL_OVERRIDE:-$(get_provider_last_model "$PROVIDER")}"

  if [[ -z "$BASE_URL" || -z "$MODEL" ]]; then
    echo "Incomplete config for provider '$PROVIDER'. Run without -c to reconfigure." >&2
    exit 1
  fi

  # Default action for continue mode is copilot
  ACTION="${ACTION:-copilot}"

  show_hint "$ACTION" "$PROVIDER" "$MODEL"
  exec env \
    COPILOT_PROVIDER_BASE_URL="$BASE_URL" \
    COPILOT_PROVIDER_API_KEY="$API_KEY" \
    COPILOT_MODEL="$MODEL" \
    copilot --continue
fi

# ============================================================================
# Mode: Fresh setup — choose provider, model, action
# ============================================================================

# --- 1. Choose or add a provider ---
if [[ ! -f "$CONFIG_FILE" ]]; then
  touch "$CONFIG_FILE"
fi

if [[ -z "$PROVIDER" ]]; then
  # Interactive: fzf selection or add new provider
  NAMES=$(get_provider_names)
  CHOICES=""
  [[ -n "$NAMES" ]] && CHOICES="$NAMES"
  CHOICES="${CHOICES}
➕ New provider"

  PICKED=$(echo "$CHOICES" | fzf --preview 'echo {}')
  [[ -z "$PICKED" ]] && echo "Aborted." >&2 && exit 1

  if [[ "$PICKED" == "➕ New provider" ]]; then
    read -rp "Provider name: " NAME
    [[ -z "$NAME" ]] && NAME="default"

    read -rp "Provider Base URL: " BASE_URL
    [[ -z "$BASE_URL" ]] && echo "Base URL is required." >&2 && exit 1

    read -rsp "API Key (optional): " API_KEY
    echo
  else
    NAME="$PICKED"
    BASE_URL=$(get_provider_url "$NAME")
    API_KEY=$(get_provider_key "$NAME")
  fi
elif [[ -z "$PROVIDER" ]]; then
  # Non-interactive without --provider: error out
  echo "No provider specified. Use --provider <name> or run with -i for interactive mode." >&2
  exit 1
else
  # Non-interactive: validate provider exists in config
  if ! get_provider_names | grep -qx "$PROVIDER"; then
    echo "Provider '$PROVIDER' not found in config." >&2
    echo "Available providers: $(get_provider_names | tr '\n' ' ')" >&2
    exit 1
  fi
  NAME="$PROVIDER"
  BASE_URL=$(get_provider_url "$NAME")
  API_KEY=$(get_provider_key "$NAME")

  if [[ -z "$BASE_URL" ]]; then
    echo "Provider '$NAME' has no URL configured." >&2
    exit 1
  fi
fi

# --- 2. Fetch available models from API (skip if --model already set) ---
MODELS=""
if [[ -z "$MODEL_OVERRIDE" ]]; then
  echo "Fetching models..."
fi
if [[ -n "$API_KEY" ]]; then
  MODELS=$(curl -s --connect-timeout 3 --max-time 5 \
    -H "Authorization: Bearer $API_KEY" "${BASE_URL}/models" 2>/dev/null | \
    jq -r '.data[].id // empty' 2>/dev/null) || true
else
  MODELS=$(curl -s --connect-timeout 3 --max-time 5 \
    "${BASE_URL}/models" 2>/dev/null | \
    jq -r '.data[].id // empty' 2>/dev/null) || true
fi

if [[ -z "$MODELS" ]]; then
  if [[ -n "$MODEL_OVERRIDE" ]]; then
    # Model was explicitly provided, use it directly
    MODELS="$MODEL_OVERRIDE"
  else
    echo "⚠️  API not responding. Using last known model from config." >&2
    LAST_MODEL=$(get_provider_last_model "$NAME")
    if [[ -n "$LAST_MODEL" ]]; then
      MODELS="$LAST_MODEL"
      echo "   Using: $LAST_MODEL"
    else
      # Fallback: ask user to type a model name
      read -rp "Enter model name (or press Enter to cancel): " MODEL
      [[ -z "$MODEL" ]] && echo "Aborted." >&2 && exit 1
      MODELS="$MODEL"
    fi
  fi
fi

# --- 3. Select model: use --model flag, fzf (interactive), or first available ---
if [[ -n "$MODEL_OVERRIDE" ]]; then
  MODEL="$MODEL_OVERRIDE"
elif [[ -z "$MODELS" ]]; then
  echo "No models available." >&2
  exit 1
else
  # Interactive mode (no --provider, no -c): let user pick via fzf
  if [[ -z "$PROVIDER" && "$CONTINUE" -eq 0 ]]; then
    MODEL=$(echo "$MODELS" | fzf --preview 'echo {}')
  else
    # Non-interactive: use first available model
    MODEL=$(echo "$MODELS" | head -1)
  fi
fi
[[ -z "$MODEL" ]] && echo "No model selected." >&2 && exit 1

# --- 4. Save provider config (for future -c mode) ---
save_provider "$NAME" "$BASE_URL" "$API_KEY" "$MODEL"
echo "Saved: provider=$NAME model=$MODEL"

# --- 5. Choose action: copilot or commit-ai ---
if [[ -z "$ACTION" ]]; then
  echo ""
  ACTION=$(printf 'copilot\ncommit-ai' | fzf --preview 'echo {}')
  [[ -z "$ACTION" ]] && echo "Aborted." >&2 && exit 1
fi

# ============================================================================
# Action: copilot — launch interactive copilot session
# ============================================================================
if [[ "$ACTION" == "copilot" ]]; then
  show_hint "copilot" "$NAME" "$MODEL"
  exec env \
    COPILOT_PROVIDER_BASE_URL="$BASE_URL" \
    COPILOT_PROVIDER_API_KEY="$API_KEY" \
    COPILOT_MODEL="$MODEL" \
    copilot
fi

# ============================================================================
# Action: commit-ai — generate and optionally commit message via LLM
# ============================================================================
if [[ "$ACTION" == "commit-ai" ]]; then
  tmpmsg=""

  # --- Validate git repo and staged changes ---
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "❌ Not in a git repository" >&2
    exit 1
  fi

  if git diff --cached --quiet; then
    echo "❌ No staged changes to commit" >&2
    exit 1
  fi

  if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    echo "❌ curl and jq are required" >&2
    exit 1
  fi

  # --- Generate diff: smart mode (default) or full mode (-f) ---
  DIFF=""
  if [[ "$FULL_DIFF" -eq 1 ]]; then
    DIFF="$(git diff --staged)"
    diff_lines=$(wc -l <<< "$DIFF")
    echo "🔍 Full diff mode ($diff_lines lines)"
  else
    # Smart mode: top 10 most modified source files with ±3 lines context
    tmpfiles=$(mktemp)
    trap 'rm -f "$tmpmsg" "$tmpfiles"' EXIT
    
    # Step 1: get file list with change counts
    git diff --name-only --staged 2>/dev/null | while IFS= read -r fname; do
      case "$fname" in
        *.lock|*.sum|README*|.gitignore|LICENSE*) continue ;;
        *.png|*.jpg|*.gif|*.ico|*.pdf) continue ;;
      esac
      cnt=$(git diff --staged "$fname" 2>/dev/null | grep '^[-+]' | grep -cv '^[+-]\{3\}' 2>/dev/null || echo 0)
      cnt=$((cnt + 0))
      printf '%s:%s\n' "$cnt" "$fname"
    done | sort -t: -k1nr | head -n 10 > "$tmpfiles"
    
    # Step 2: build diff output
    DIFF=""
    while IFS=: read -r cnt fname; do
      [[ -z "$fname" ]] && continue
      DIFF+="--- $fname ---\n"
      DIFF+=$(git diff --staged -U3 "$fname" 2>/dev/null | head -n 60 || true)
      DIFF+="\n"
    done < "$tmpfiles"
    
    local_file_count=$(git diff --name-only --staged 2>/dev/null | wc -l)
    src_files=$(echo "$DIFF" | grep -c '^---' 2>/dev/null || echo 0)
    src_files=${src_files:-0}
    echo "🔍 Smart mode: $src_files source files ($local_file_count total changed, ~10 most modified selected)"
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
    response=$(curl -fsS --connect-timeout 10 --max-time 120 \
      -w "\n%{http_code}" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${API_KEY}" \
      -d "$payload" "${BASE_URL}/chat/completions" 2>&1 || true)
  else
    response=$(curl -fsS --connect-timeout 10 --max-time 120 \
      -w "\n%{http_code}" \
      -H "Content-Type: application/json" \
      -d "$payload" "${BASE_URL}/chat/completions" 2>&1 || true)
  fi

  http_code=$(echo "$response" | tail -1)
  if [[ "$http_code" != "200" ]]; then
    echo "❌ API returned HTTP $http_code" >&2
    echo "$response" | head -20 >&2
    exit 1
  fi

  response=$(echo "$response" | sed '$d')

  if [[ -z "$response" ]] || ! printf '%s' "$response" | jq -e '.choices' >/dev/null 2>&1; then
    echo "❌ API request failed: invalid JSON response" >&2
    echo "$response" | head -20 >&2
    exit 1
  fi

  # --- Extract commit message from API response ---
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
  ' 2>&1) || { echo "❌ jq parsing failed" >&2; echo "$response" | head -20 >&2; exit 1; }

  # Trim leading empty lines
  message="$(printf '%s' "$message" | sed -e '/./,$!d')"

  if [[ -z "$message" ]]; then
    echo "❌ Failed to generate commit message" >&2
    exit 1
  fi

  # Add signoff if git user is configured
  name=$(git config user.name || true)
  email=$(git config user.email || true)
  if [[ -n "$name" && -n "$email" ]]; then
    message="$message"$'\n\n'"Signed-off-by: $name <$email>"
  fi

  # --- Mode: dry-run — show message, exit without committing ---
  if [[ "$DRY_RUN" -eq 1 ]]; then
    show_hint "commit-ai" "$NAME" "$MODEL" "--no-edit"
    echo ""
    echo "📝 Generated commit message:"
    echo "$message" | sed 's/^/   /'
    rm -f "$tmpfiles"
    exit 0
  fi

  # --- Mode: no-edit — commit directly without editor ---
  if [[ "$NO_EDIT" -eq 1 ]]; then
    show_hint "commit-ai" "$NAME" "$MODEL" "--no-edit"
    git commit -m "$message"
    echo "✅ Commit created!"
    exit 0
  fi

  # --- Mode: interactive — open editor for review/edit ---
  tmpmsg=$(mktemp)
  trap 'rm -f "$tmpmsg"' EXIT
  printf '%s\n' "$message" > "$tmpmsg"

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
    [[ "$ans" =~ ^[Nn]$ ]] && echo "Canceled" >&2 && exit 1
    git commit -m "$(cat "$tmpmsg")"
  }

  try_editor || true

  edited=$(cat "$tmpmsg")
  if [[ -z "$(printf '%s' "$edited" | tr -d '[:space:]')" ]]; then
    echo "❌ Commit canceled (message empty)" >&2
  else
    show_hint "commit-ai" "$NAME" "$MODEL" "--no-edit"
    git commit -m "$edited"
    echo "✅ Commit created!"
  fi
fi
