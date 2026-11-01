#!/usr/bin/env bash

# Install zsh if needed
echo "inastall zsh if not exit - $(apt install zsh)"
if command -v zsh &> /dev/null; then
    echo "✅ zsh is already installed"
else
    echo "zsh is not installed"
    echo "installing zsh"
    apt install zsh
    zsh
    chsh -s $(which zsh)
fi

echo "Done! Reload terminal to apply  changes."
