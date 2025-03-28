if [[ "$OSTYPE" == "darwin"* ]]; then
  ZSH_THEME="robbyrussell"  # macOS
else
  ZSH_THEME="bureau"      # Другая ОС (Linux, Windows WSL и т. д.)
fi
plugins=(
  git
  brew
  aliases
  colorize
  dotenv
  zsh-autosuggestions
  you-should-use
  zsh-syntax-highlighting
  tmux
)
export ZSH="$HOME/.oh-my-zsh"

source $ZSH/oh-my-zsh.sh
