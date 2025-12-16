#!/usr/bin/env bash

# Install fresh oh-my-zsh and add to current zshrc
git clone https://github.com/ohmyzsh/ohmyzsh.git ~/.oh-my-zsh
cd ~/.oh-my-zsh && git pull && cd -
touch ~/.new_zshrc
echo "export USE_OH_MY_ZSH='true'" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/.minimal.zshrc)" >>~/.new_zshrc
echo "$(cat ~/.dotfiles/.zshrc)" >>~/.new_zshrc
cp ~/.new_zshrc ~/.zshrc
rm -rf ~/.new_zshrc

git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/MichaelAquilina/zsh-you-should-use.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/you-should-use
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

echo "inastall zsh if not exit - \$(apt install zsh)"
echo "Done! Reload terminal to apply  changes."
