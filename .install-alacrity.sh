#!/bin/bash

echo "🚀 Установка Alacritty на macOS..."

# 1. Установка Alacritty через Homebrew
if ! command -v brew &>/dev/null; then
  echo "❌ Homebrew не найден! Установите его сначала: https://brew.sh"
  exit 1
fi

echo "📦 Устанавливаем Alacritty..."
brew install --cask alacritty
brew tap homebrew/cask-fonts
brew install --cask font-jetbrains-mono-nerd-font

# 2. Создание папки конфигурации
CONFIG_DIR="$HOME/.config/alacritty"
CONFIG_FILE="$CONFIG_DIR/alacritty.yml"

mkdir -p "$CONFIG_DIR"

# 3. Запись конфигурации в alacritty.yml
echo "⚙️ Настраиваем Alacritty..."

cat <<EOF >"$CONFIG_FILE"
font:
  normal:
    family: "FiraCode Nerd Font"
    style: Regular
  size: 14

colors:
  primary:
    background: "#1E1E1E"
    foreground: "#C7C7C7"

window:
  padding:
    x: 10
    y: 10
  dynamic_padding: true
EOF

echo "✅ Конфигурация Alacritty создана в $CONFIG_FILE"

# 4. Установка Nerd Fonts (необходим для красивых символов)
echo "🔤 Устанавливаем Nerd Fonts..."
brew tap homebrew/cask-fonts
brew install --cask font-fira-code-nerd-font

# 5. Добавление Alacritty в Applications
echo "📂 Добавляем Alacritty в Applications..."
cp -r /opt/homebrew/Cellar/alacritty/*/Alacritty.app /Applications/ 2>/dev/null ||
  cp -r /usr/local/Cellar/alacritty/*/Alacritty.app /Applications/ 2>/dev/null

# 6. Вывод завершения установки
echo "🎉 Alacritty установлен и настроен!"
echo "Запустите терминал командой: alacritty"
