if [[ "$OSTYPE" == "darwin"* ]]; then
  ZSH_THEME="bakhbk"             # macOS (robbyrussell + часы)
else
  ZSH_THEME="bureau"      # Другая ОС (Linux, Windows WSL и т. д.)
fi
plugins=(
  web-search
  git-flow
  brew
  aliases
  colorize
  zsh-autosuggestions
  you-should-use
  zsh-syntax-highlighting
  tmux
  uv
  git
)
# Плагины, которые имеют смысл только если соответствующая программа установлена
command -v tmux >/dev/null 2>&1 || plugins=(${plugins:#tmux})
command -v brew >/dev/null 2>&1 || plugins=(${plugins:#brew})

export ZSH="$HOME/.oh-my-zsh"

source $ZSH/oh-my-zsh.sh
