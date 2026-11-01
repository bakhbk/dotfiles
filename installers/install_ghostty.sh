#!/usr/bin/env bash
# Ghostty + terminfo setup for the whole fleet (macOS/Linux, idempotent).
#   ./installers/install_ghostty.sh          # install/configure
#   ./installers/install_ghostty.sh --check  # диагностика, ничего не меняет
#
# Почему это нужно: tmux копирует в системный буфер через OSC 52, но только
# если terminfo-запись терминала объявляет возможность Ms (и XT). На серверах
# её нет -> "y" в tmux копирует в буфер tmux, а не в буфер macOS.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

OS="$(uname -s)"
say()  { echo "$1"; }
warn() { echo "⚠️  $1" >&2; }

# ---------------------------------------------------------------- binary
if [[ "$OS" == "Darwin" ]]; then
  export PATH="/opt/homebrew/bin:$PATH"
  if command -v brew >/dev/null 2>&1; then
    if ! ls /Applications/Ghostty.app >/dev/null 2>&1; then
      if ((CHECK_ONLY)); then warn "Ghostty не установлен"; else
        brew install --cask ghostty
      fi
    fi
    if ! command -v tmux >/dev/null 2>&1; then
      if ((CHECK_ONLY)); then warn "tmux не установлен"; else brew install tmux; fi
    fi
  else
    warn "Homebrew не найден — установи Ghostty вручную"
  fi
else
  if ! command -v ghostty >/dev/null 2>&1; then
    if ((CHECK_ONLY)); then
      warn "ghostty не установлен"
    elif command -v apt-get >/dev/null 2>&1; then
      sudo -n apt-get install -y ghostty 2>/dev/null || {
        # Ubuntu < 26.04: ghostty нет в основном репозитории — берём PPA
        if command -v add-apt-repository >/dev/null 2>&1; then
          sudo -n add-apt-repository -y ppa:mkasberg/ghostty-ubuntu &&
            sudo -n apt-get update -qq && sudo -n apt-get install -y ghostty
        else
          warn "apt: ghostty не найден; нужна software-properties-common (sudo apt install software-properties-common)"
        fi
      }
    elif command -v dnf >/dev/null 2>&1; then
      dnf install -y ghostty 2>/dev/null || warn "dnf: ghostty не найден"
    elif command -v pacman >/dev/null 2>&1; then
      pacman -Sy --noconfirm ghostty 2>/dev/null || warn "pacman: ghostty не найден"
    else
      warn "нет подходящего пакетного менеджера"
    fi
  fi
fi

# ---------------------------------------------------------------- terminfo
have_entry() { infocmp xterm-ghostty >/dev/null 2>&1; }

# Источник «правильного» terminfo, по предпочтению:
#  1) бандл Ghostty (полный набор capabilities: setaf, smkx, el, Ms)
#  2) уже установленный в системе (ncurses >= 6.5 / Ubuntu 26.04)
#  3) fallback: клон xterm-256color + XT/Ms/Su
GHOSTTY_TERMINFO=""
for p in /Applications/Ghostty.app/Contents/Resources/terminfo \
         "$HOME/.local/share/terminfo" /usr/share/terminfo; do
  if TERMINFO="$p" infocmp -x xterm-ghostty 2>/dev/null | grep -q 'setaf='; then
    GHOSTTY_TERMINFO="$p"; break
  fi
done

if have_entry && infocmp -x xterm-ghostty 2>/dev/null | grep -q 'setaf='; then
  say "✅ terminfo xterm-ghostty уже есть и полный"
else
  out=$(mktemp)
  if [[ -n "$GHOSTTY_TERMINFO" ]]; then
    TERMINFO="$GHOSTTY_TERMINFO" infocmp -x xterm-ghostty > "$out"
  else
    say "⚠️  своей записи нет — собираем из xterm-256color + XT/Ms"
    infocmp -x xterm-256color > "$out"
    python3 - "$out" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().split('\n')
lines[0] = 'xterm-ghostty|ghostty|Ghostty terminal emulator,'
body = [l for l in lines[1:] if l.strip()]
body.append('\tXT,')
body.append('\tMs=\E]52;%p1%s;%p2%s\007,')
open(p, 'w').write('\n'.join(body) + '\n')
PY
  fi
  if sudo -n tic -x "$out" 2>/dev/null; then
    say "✅ terminfo установлен в /usr/share/terminfo"
  else
    mkdir -p "$HOME/.terminfo"
    TERMINFO="$HOME/.terminfo" tic -x "$out" && say "✅ terminfo установлен в $HOME/.terminfo"
  fi
  rm -f "$out"
  infocmp xterm-ghostty >/dev/null 2>&1 || warn "tic выполнил, но infocmp не видит запись"
fi

# ---------------------------------------------------------------- config
CONFIG="$HOME/.config/ghostty/config"
if [[ -f "$REPO_DIR/ghostty/config" ]] && ((CHECK_ONLY == 0)); then
  mkdir -p "$HOME/.config/ghostty"
  cp -f "$REPO_DIR/ghostty/config" "$CONFIG"
  say "✅ ghostty config -> $CONFIG"
fi

# ---------------------------------------------------------------- report
tmux_ver=$(tmux -V 2>/dev/null || echo "нет")
say "tmux: $tmux_ver (нужен >= 3.2 для OSC 52)"
if infocmp -x xterm-ghostty 2>/dev/null | grep -qE 'Ms='; then
  say "✅ OSC 52 (Ms) объявлен в terminfo -> tmux сам пробросит копирование"
else
  warn "OSC 52 не объявлен: нужна страховка 'set -g terminal-features \",xterm-ghostty:clipboard\"' в .tmux.conf"
fi
