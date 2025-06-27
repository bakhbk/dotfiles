# Purprose:
# zsh configuration.

# Don't beep on errors
setopt No_Beep

# History parameters
# It is recommended to keep SAVEHIST == HISTSIZE
HISTSIZE=100000
SAVEHIST=100000
HISTFILE=~/.dotfiles/.zsh_history

# Сохранять историю между сессиями
setopt SHARE_HISTORY

# Не дублировать команды в истории
setopt HIST_IGNORE_DUPS

# Сохранять время выполнения команд
setopt EXTENDED_HISTORY

# Each line is added to the history as it is executed
setopt INC_APPEND_HISTORY

# Removes copies of lines still in the history list
setopt HIST_IGNORE_ALL_DUPS

# Drop empty strings from history
setopt HIST_REDUCE_BLANKS

# Remove no needed spaces (e.g. trailing)
setopt HIST_IGNORE_SPACE

# Не сохранять команды, начинающиеся с пробела (полезно для паролей)
setopt HIST_IGNORE_SPACE

# Проверять команды истории перед выполнением
setopt HIST_VERIFY

# Не сохранять команду history в истории
setopt HIST_NO_STORE

# Не выполнять функцию history expansion сразу, позволить редактировать
setopt HIST_VERIFY

# Удалять старые дубликаты при достижении HISTSIZE
setopt HIST_EXPIRE_DUPS_FIRST

# Игнорировать некоторые часто используемые команды
HISTORY_IGNORE="(ls|cd|pwd|exit|sudo reboot|history|cd -|cd ..)"

# Функции для работы с историей
# Поиск в истории с fzf (если установлен)
function fh() {
  print -z $( ([ -n "$ZSH_NAME" ] && fc -l 1 || history) | fzf +s --tac | sed -E 's/ *[0-9]*\*? *//' | sed -E 's/\\/\\\\/g')
}

# Очистка истории
function clear_history() {
    echo "Очищаю историю команд..."
    echo "" > ~/.dotfiles/.zsh_history
    fc -p ~/.dotfiles/.zsh_history
    echo "История очищена!"
}

# Статистика по самым используемым командам
function history_stats() {
    fc -l 1 | awk '{CMD[$2]++;count++;}END { for (a in CMD)print CMD[a] " " CMD[a]/count*100 "% " a;}' | grep -v "./" | column -c3 -s " " -t | sort -nr | nl |  head -n20
}

# Поиск команды в истории
function hist_grep() {
    fc -l 1 | grep "$@"
}

# Expand PATH
typeset -U path

# Load scripts
source ~/.dotfiles/.zsh_aliases
source ~/.dotfiles/.zsh_tools
source ~/.dotfiles/.zshenv
source ~/.dotfiles/.create_tmux_session.sh
source ~/.dotfiles/.zsh_history_config
if [ -f ~/work/.zshrc ]; then
  source ~/work/.zshrc
fi


path=()
path+=(~/.local/bin)

if [[ "${OSTYPE}" = darwin* ]]; then
    path+=("${HOMEBREW_PREFIX}/bin")
    path+=("${HOMEBREW_PREFIX}/opt/coreutils/libexec/gnubin")
    path+=("${HOMEBREW_PREFIX}/opt/gnu-tar/libexec/gnubin")
    path+=("${HOMEBREW_PREFIX}/opt/openjdk/bin")
    path+=("${HOMEBREW_PREFIX}/opt/unzip/bin")
    path+=("${HOMEBREW_PREFIX}/opt/ruby/bin")
fi

path+=(/usr/local/bin)
path+=(/usr/local/sbin)
path+=(/usr/bin)
path+=(/bin)
path+=(/usr/sbin)
path+=(/sbin)

# Tramp client (Emacs) sets TERM to dumb.
# It doesn't expect anything clever or beautiful if cmdline prompt.
if [[ $TERM == "dumb" ]]; then
    unsetopt zle
    PS1='$ '
    return
fi

if [[ $USE_OH_MY_ZSH == "true" ]]; then
    # echo 'USE_OH_MY_ZSH user ' $USE_OH_MY_ZSH
else 
    # echo 'USE_OH_MY_ZSH NOT used ' $USE_OH_MY_ZSH
    source ~/.dotfiles/.shell_prompt
fi

# fzf is a general-purpose command-line fuzzy finder.
# https://github.com/junegunn/fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh && source <(fzf --zsh)

if command -v pyenv >/dev/null; then
    export PYENV_ROOT="$HOME/.pyenv"
    PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
fi

if command -v git >/dev/null; then
    git config --global core.editor "vim"
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"                   # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" # This loads nvm bash_completion

export PATH="$HOME/fvm/default/bin:$PATH"
export PATH="$PATH":"$HOME/.pub-cache/bin"

if command -v go >/dev/null; then
    export PATH="$PATH:$(go env GOPATH)/bin"
fi
