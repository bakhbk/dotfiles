#!/usr/bin/env bash

# Install fresh oh-my-zsh and add to current zshrc
git clone https://github.com/ohmyzsh/ohmyzsh.git ~/.oh-my-zsh
cd ~/.oh-my-zsh && git pull && cd -
touch ~/.new_zshrc
echo "export USE_OH_MY_ZSH='true'" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/minimal.zshrc)" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/.zshrc)" >>~/.new_zshrc
cp ~/.new_zshrc ~/.zshrc
rm -rf ~/.new_zshrc

git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/MichaelAquilina/zsh-you-should-use.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/you-should-use
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

# Custom themes: копируем из dotfiles (источник: shell/themes/)
mkdir -p ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/themes
cp -f "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/shell/themes/*.zsh-theme ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/themes/

# Install zsh if it is not present
if ! command -v zsh >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y zsh
    elif command -v brew >/dev/null 2>&1; then
        brew install zsh
    fi
fi
echo "Done! Reload terminal to apply  changes."
