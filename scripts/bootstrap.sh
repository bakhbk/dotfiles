#!/usr/bin/env bash

# Purpose:
# Install or remove development tools based on user selection.
#
#   ./scripts/bootstrap.sh --install          # interactive prompts allowed
#   ./scripts/bootstrap.sh --install --yes    # fully non-interactive
#   DOTFILES_ASSUME_YES=1 ./scripts/bootstrap.sh --install

set -euxo pipefail

# Nested installers must not ask anything once the user consented
ASSUME_YES=${DOTFILES_ASSUME_YES:-0}
ACTION=""
for arg in "$@"; do
  case "$arg" in
    --install | -i) ACTION=install ;;
    --clean | -c) ACTION=clean ;;
    --yes | -y) ASSUME_YES=1 ;;
    *) echo "ℹ️ Неизвестный аргумент: $arg" ;;
  esac
done

if [[ -z "$ACTION" ]]; then
  echo "❌ Использование: $0 --install [-y] | --clean [-y]"
  exit 1
fi

export DOTFILES_ASSUME_YES="$ASSUME_YES"
export HOMEBREW_NO_ASK=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export DEBIAN_FRONTEND=noninteractive

# Helper: run a command without letting it prompt for input
run_no_prompt() {
  if [[ "$ASSUME_YES" == "1" ]]; then
    "$@" < /dev/null
  else
    "$@"
  fi
}
# Определяем ОС
OS=$(uname -s)

# Определяем пакетный менеджер
if [[ "$OS" == "Darwin" ]]; then
  PACKAGE_MANAGER="brew"
elif command -v apt >/dev/null; then
  PACKAGE_MANAGER="apt"
elif command -v dnf >/dev/null; then
  PACKAGE_MANAGER="dnf"
elif command -v pacman >/dev/null; then
  PACKAGE_MANAGER="pacman"
else
  echo "❌ Неизвестный пакетный менеджер."
  exit 1
fi

# Список пакетов для установки/удаления
PACKAGES=("zsh" "bat" "shellcheck" "btop" "coreutils" "tmux" "neovim" "zsh-syntax-highlighting" "glow" "mdless")

# Специальные пакеты для Linux
if [[ "$OS" == "Linux" ]]; then
  PACKAGES+=("inetutils-traceroute" "inetutils-telnet" "inetutils-ftp" "inetutils-ping" "tftpd-hpa")
elif [[ "$OS" == "Darwin" ]]; then
  PACKAGES+=("inetutils")
fi

# Функция установки пакетов
install_packages() {
  if [[ "$OS" == "Darwin" ]]; then
    if ! command -v brew >/dev/null; then
      echo "📦 Устанавливаем Homebrew..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      eval "$(/opt/homebrew/bin/brew shellenv)"
      brew cleanup --prune=all
    fi
  fi

  echo "📦 Устанавливаем пакеты..."
  for package in "${PACKAGES[@]}"; do
    if command -v "$package" >/dev/null 2>&1; then
      echo "✅ $package уже установлен, пропускаем..."
    else
      if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
        # HOMEBREW_NO_ASK=1 (exported above)suppresses the
        # "Do you want to proceed with the installation? [y/n]" prompt
        brew install "$package"
      elif [[ "$PACKAGE_MANAGER" == "apt" ]]; then
        sudo apt update && sudo apt install -y "$package"
      elif [[ "$PACKAGE_MANAGER" == "dnf" ]]; then
        sudo dnf install -y "$package"
      elif [[ "$PACKAGE_MANAGER" == "pacman" ]]; then
        sudo pacman -S --noconfirm "$package"
      fi
    fi
  done

  # Установка FVM
  if ! command -v fvm >/dev/null; then
    if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
      brew tap leoafarias/fvm
      brew install fvm
    else
      echo "📦 Устанавливаем FVM..."
      curl -fsSL https://fvm.app/install.sh | bash
      echo 'export PATH="$HOME/.pub-cache/bin:$PATH"' >>~/.zshrc
      export PATH="$HOME/.pub-cache/bin:$PATH"
    fi
  else
    echo "✅ FVM уже установлен, пропускаем..."
  fi
}

# Функция удаления пакетов
remove_packages() {
  echo "🗑 Удаляем пакеты..."
  for package in "${PACKAGES[@]}"; do
    if command -v "$package" >/dev/null 2>&1; then
      if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
        brew uninstall --ignore-dependencies "$package"
      elif [[ "$PACKAGE_MANAGER" == "apt" ]]; then
        sudo apt remove -y "$package"
      elif [[ "$PACKAGE_MANAGER" == "dnf" ]]; then
        sudo dnf remove -y "$package"
      elif [[ "$PACKAGE_MANAGER" == "pacman" ]]; then
        sudo pacman -Rns --noconfirm "$package"
      fi
    else
      echo "❌ $package не найден, пропускаем..."
    fi
  done
}

# Установка uv и команды prep (синхронизация моделей AI-агентов)
install_uv_and_prep() {
  REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  run_no_prompt "$REPO_DIR/installers/install_uv.sh" || echo "⚠️ uv не установлен — prep будет работать только через ~/dotfiles/installers/install_uv.sh"
  run_no_prompt "$REPO_DIR/installers/install_prep.sh" || echo "⚠️ prep не настроен"
}

# Функция установки и обновления ZSH-плагинов
install_zsh_plugins() {
  install_or_update_zsh_plugin() {
    if [ -d ~/.zsh/"${2}" ]; then
      cd ~/.zsh/"${2}"
      git pull
      cd -
      return
    fi
    git clone "${1}" "${HOME}/.zsh/${2}"
  }

  echo "📦 Устанавливаем ZSH плагины..."
  install_or_update_zsh_plugin https://github.com/MichaelAquilina/zsh-you-should-use.git zsh-you-should-use
  install_or_update_zsh_plugin https://github.com/zsh-users/zsh-syntax-highlighting.git zsh-syntax-highlighting
  install_or_update_zsh_plugin https://github.com/zsh-users/zsh-autosuggestions.git zsh-autosuggestions
  install_or_update_zsh_plugin https://github.com/fdellwing/zsh-bat.git zsh-bat
  install_or_update_zsh_plugin https://gist.github.com/5013acf2cd5b28e55036c82c91bd56d8.git adb-commands

  if ! grep -q "source ~/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ~/.zshrc; then
    echo 'source ~/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh' >>~/.zshrc
  fi
}

# Настройки Finder для macOS
configure_macos() {
  echo "⚙️ Применяем настройки Finder..."
  defaults write NSGlobalDomain AppleShowAllExtensions -bool true
  defaults write com.apple.Finder AppleShowAllFiles -bool true
  defaults write com.apple.Finder NewWindowTarget -string "PfHm"
  defaults write com.apple.Finder NewWindowTargetPath -string "file:///Users/${USER}/"
  defaults write com.apple.Finder ShowStatusBar -bool false
  defaults write com.apple.Finder _FXShowPosixPathInTitle -bool true
  defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false
  defaults write com.apple.finder ShowPathbar -bool true
  defaults write com.apple.finder _FXSortFoldersFirst -bool true
  killall Finder

  # Разрешить длительное нажатие клавиш
  defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false
}

# Восстановление стандартных настроек macOS при очистке
restore_macos_defaults() {
  echo "🔄 Восстанавливаем стандартные настройки macOS..."
  defaults delete NSGlobalDomain AppleShowAllExtensions || true
  defaults delete com.apple.Finder AppleShowAllFiles || true
  defaults delete com.apple.Finder NewWindowTarget || true
  defaults delete com.apple.Finder NewWindowTargetPath || true
  defaults delete com.apple.Finder ShowStatusBar || true
  defaults delete com.apple.Finder _FXShowPosixPathInTitle || true
  defaults delete com.apple.finder FXEnableExtensionChangeWarning || true
  defaults delete com.apple.finder ShowPathbar || true
  defaults delete com.apple.finder _FXSortFoldersFirst || true
  killall Finder

  # Восстанавливаем стандартное поведение клавиш
  defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool true
}

# Главный блок: действие определено в начале файла
case "$ACTION" in
  install)
    echo "🚀 Запуск установки..."
    install_packages
    install_uv_and_prep
    install_zsh_plugins
    if [[ "$OS" == "Darwin" ]]; then
      configure_macos
    fi
    echo "✅ Установка завершена!"
    ;;
  clean)
    echo "🗑 Запуск очистки..."
    remove_packages
    if [[ "$OS" == "Darwin" ]]; then
      restore_macos_defaults
    fi
    echo "✅ Очистка завершена!"
    ;;
  *)
    echo "❌ Неверный аргумент. Используйте: $0 --install | -i | --clean | -c"
    exit 1
    ;;
esac
