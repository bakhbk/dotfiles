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

# OH MY ZSH плагин = каталог с именем plugin, внутри которого лежит <plugin>.plugin.zsh
# Поэтому клонируем в имя плагина, а не в имя репозитория (repo -> plugin)
# (например MichaelAquilina/zsh-you-should-use -> plugins/you-should-use)
custom="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
for entry in "zsh-users/zsh-autosuggestions:zsh-autosuggestions" \
             "MichaelAquilina/zsh-you-should-use:you-should-use" \
             "zsh-users/zsh-syntax-highlighting:zsh-syntax-highlighting"; do
  repo="${entry%%:*}"
  plugin="${entry##*:}"
  old="$custom/$(basename "$repo")"
  # Миграция: раньше каталог назывался по имени репозитория (zsh-you-should-use)
  if [ -d "$old" ] && [ "$old" != "$custom/$plugin" ] && [ ! -d "$custom/$plugin" ]; then
    mv "$old" "$custom/$plugin"
  fi
  if [ -d "$custom/$plugin" ]; then
    (cd "$custom/$plugin" && git pull --ff-only) || true
  else
    git clone "https://github.com/$repo" "$custom/$plugin"
  fi
done

# Custom themes: копируем из dotfiles (источник: shell/themes/)
themes_dir=""
sd="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for cand in "$sd/../shell/themes" "$sd/themes" "$sd" "$HOME/.dotfiles/themes" "$HOME/.dotfiles"; do
  if [ -d "$cand" ] && ls "$cand"/*.zsh-theme >/dev/null 2>&1; then
    themes_dir="$cand"
    break
  fi
done
if [ -n "$themes_dir" ]; then
  mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes"
  cp -f "$themes_dir"/*.zsh-theme "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/"
else
  echo "⚠️ Custom themes не найдены (shell/themes/*.zsh-theme) — пропускаем"
fi

# Install zsh if it is not present
if ! command -v zsh >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y zsh
    elif command -v brew >/dev/null 2>&1; then
        brew install zsh
    fi
fi
echo "Done! Reload terminal to apply  changes."
