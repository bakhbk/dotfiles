#!/usr/bin/env bash
# Non-interactive: пользователь уже согласился на установку (см. install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive

# Make the `prep` command available on this machine.
#  1. Remember where the dotfiles repo lives (DOTFILES_DIR).
#  2. Install uv.
#  3. Create a ~/.local/bin/prep wrapper (works in zsh, bash, tmux, etc.).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREP_SCRIPT="$REPO_DIR/scripts/prep-agents/prep-agents.py"

if [[ ! -f "$PREP_SCRIPT" ]]; then
  echo "❌ Не найден $PREP_SCRIPT — клон dotfiles неполный? Выполните: git pull" >&2
  exit 1
fi

echo "📦 Подготовка prep (репозиторий: $REPO_DIR)"

# 1. Where the repo is — sourced by ~/.zshrc / ~/.bashrc
mkdir -p "$HOME/.dotfiles"
{
  echo "# Автоматически сгенерировано installers/install_prep.sh — не редактировать"
  echo "export DOTFILES_DIR=\"$REPO_DIR\""
} > "$HOME/.dotfiles/dotfiles.env"

# 2. uv
"$REPO_DIR/installers/install_uv.sh" || true

# 3. Wrapper in ~/.local/bin (already on PATH in .zshrc)
mkdir -p "$HOME/.local/bin"
{
  cat <<'EOF'
#!/usr/bin/env bash
# prep — синхронизация моделей AI-агентов из dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
SCRIPT="$DOTFILES_DIR/scripts/prep-agents/prep-agents.py"
if [[ ! -f "$SCRIPT" ]]; then
  echo "❌ prep: не найден $SCRIPT (dotfiles не установлен в ~/dotfiles)" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "❌ prep: не найден uv. Выполните: ~/dotfiles/installers/install_uv.sh" >&2
  exit 1
fi
exec uv run "$SCRIPT" "$@"
EOF
} > "$HOME/.local/bin/prep"
chmod +x "$HOME/.local/bin/prep"

# 4. Convenience wrappers for the context-size presets
for preset in fast:8000 code:16000 deep:32000 big:64000 clean:cleanup; do
  name="${preset%%:*}"
  value="${preset##*:}"
  cat > "$HOME/.local/bin/prep-$name" <<EOF
#!/usr/bin/env bash
if [ "$name" = "clean" ]; then
  exec prep --cleanup "\$@"
fi
exec prep --max-context $value "\$@"
EOF
  chmod +x "$HOME/.local/bin/prep-$name"
done

echo "✅ prep готов: 'prep', 'prep-fast', 'prep-code', 'prep-deep', 'prep-big', 'prep-clean'"
