# Restore ASCII charset after ncurses/TUI programs (qemu -curses, vim, tmux)
# that leave the terminal in DEC special graphics mode: letters render as box glyphs.

fixterm() {
    printf '\033(B\033[0m'
    stty sane 2>/dev/null
}

precmd_functions+=(fixterm)
