#!/usr/bin/env bash
# Non-interactive: пользователь уже согласился на установку (см. install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive

# Install fresh oh-my-zsh and add to current zshrc
[ -d ~/.oh-my-zsh ] || git clone https://github.com/ohmyzsh/ohmyzsh.git ~/.oh-my-zsh
cd ~/.oh-my-zsh && git pull && cd -
touch ~/.new_zshrc
echo "export USE_OH_MY_ZSH='true'" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/minimal.zshrc)" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/.zshrc)" >>~/.new_zshrc
cp ~/.new_zshrc ~/.zshrc
rm -rf ~/.new_zshrc

for repo in zsh-users/zsh-autosuggestions MichaelAquilina/zsh-you-should-use zsh-users/zsh-syntax-highlighting; do
  name=$(basename "$repo")
  custom="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
  [ -d "$custom/$name" ] || git clone "https://github.com/$repo" "$custom/$name"
done

# Custom themes: копируем из dotfiles (источник: shell/themes/)
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes"
cp -f "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/shell/themes/*.zsh-theme "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/"

# Install zsh if it is not present
if ! command -v zsh >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y zsh
    elif command -v brew >/dev/null 2>&1; then
        brew install zsh
    fi
fi
echo "Done! Reload terminal to apply  changes."
