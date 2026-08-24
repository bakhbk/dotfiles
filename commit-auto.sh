#!/usr/bin/env bash
# ============================================================================
# commit-auto — git-flow style commit (type from branch, issue from branch/desc)
# Usage:
#   commit-auto.sh -u "https://tracker.example.com/issue/" -d "proj-123 implement user authentication"
#   commit-auto.sh -t fix -u "https://tracker.example.com/issue/" -d "proj-123 implement user authentication"
# ============================================================================

set -euo pipefail

DESC=""
TYPE_OVERRIDE=""
URL_BASE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -d|--desc)   DESC="$2"; shift 2 ;;
    -t|--type)   TYPE_OVERRIDE="$2"; shift 2 ;;
    -u|--url)    URL_BASE="$2"; shift 2 ;;
    *)           echo "❌ Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# --- Validate git repo and staged changes ---
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "❌ Not in a git repository" >&2
  exit 1
fi

if git diff --cached --quiet; then
  echo "❌ No staged changes to commit" >&2
  exit 1
fi

# --- Get current branch name ---
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "❌ Could not determine current branch" >&2
  exit 1
fi

# --- Determine commit type from branch prefix or -t override ---
if [[ -n "$TYPE_OVERRIDE" ]]; then
  TYPE="$TYPE_OVERRIDE"
else
  case "$BRANCH" in
    feature/*)   TYPE="feat" ;;
    fix/*|bugfix/*) TYPE="fix" ;;
    hotfix/*)    TYPE="fix" ;;
    release/*)   TYPE="chore" ;;
    *)           echo "❌ Unknown branch prefix: $BRANCH (expected feature/, fix/, hotfix/, release/). Use -t to override." >&2; exit 1 ;;
  esac
fi

# --- Extract issue-id from branch name (pattern: word-digits) ---
ISSUE_ID=""
if [[ "$BRANCH" =~ ([a-zA-Z]+-[0-9]+) ]]; then
  ISSUE_ID="${BASH_REMATCH[1]}"
fi

# --- Validate inputs ---
if [[ -z "$DESC" ]]; then
  echo "❌ Description required. Use: commit-auto.sh -d \"proj-123 implement user authentication\""
  exit 1
fi

if [[ -z "$URL_BASE" ]]; then
  echo "❌ URL base required. Use: commit-auto.sh -u \"https://tracker.example.com/issue/\""
  exit 1
fi

# If issue-id not in branch, try to extract from DESC
if [[ -z "$ISSUE_ID" ]]; then
  if [[ "$DESC" =~ ([a-zA-Z]+-[0-9]+) ]]; then
    ISSUE_ID="${BASH_REMATCH[1]}"
  else
    echo "❌ Could not find issue-id in branch name or description. Use format: proj-123 implement user authentication" >&2
    exit 1
  fi
else
  # Issue-id already in branch — remove it from DESC to avoid duplication
  DESC="${DESC#*$ISSUE_ID}"
  DESC="$(echo "$DESC" | sed 's/^[[:space:]]*//')"
fi

# --- Build commit message ---
NAME=$(git config user.name || true)
EMAIL=$(git config user.email || true)

MESSAGE="${TYPE}: ${ISSUE_ID} ${DESC}"
MESSAGE+=$'\n\n'
MESSAGE+="${URL_BASE}${ISSUE_ID}"

if [[ -n "$NAME" && -n "$EMAIL" ]]; then
  MESSAGE+=$'\n\n'
  MESSAGE+="Signed-off-by: ${NAME} <${EMAIL}>"
fi

# --- Show and commit ---
echo "📝 Commit message:"
echo ""
echo "=================="
echo "$MESSAGE" | sed 's/^/| /'
echo "=================="
echo ""

git commit -m "$MESSAGE"
echo "✅ Commit created!"
