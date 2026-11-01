# 1) Guard: если terminfo-запись текущего TERM отсутствует или неполна
#    (классика: TERM=xterm-ghostty на хосте, где нет такой записи) — zle
#    не знает setaf/el/smkx, промпт и autosuggestions рисуют мусор ("?➜",
#    дублирование символов). Falling back к xterm-256color это чинит.
# 2) Restore ASCII charset после ncurses/TUI-программ (vim, tmux, qemu-curses),
#    которые оставляют терминал в DEC special graphics режиме.

term_guard() {
  [[ -z "${TERM:-}" || "$TERM" == "dumb" || "$TERM" == "unknown" ]] && return 0
  command -v infocmp >/dev/null 2>&1 || return 0
  caps=$(infocmp -1 "$TERM" 2>/dev/null)
  if [[ -z "$caps" || "${caps}" != *setaf=* ]]; then
    export TERM=xterm-256color
  fi
}

term_guard

fixterm() {
    printf '\033(B\033[0m'
    stty sane 2>/dev/null
}

precmd_functions+=(fixterm)
