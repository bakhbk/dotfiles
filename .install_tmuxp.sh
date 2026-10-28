#!/bin/bash
# Non-interactive: пользователь уже согласился на установку (см. install.sh)
export HOMEBREW_NO_ASK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 DEBIAN_FRONTEND=noninteractive

# Проверяем, установлен ли tmuxp
if brew list tmuxp &>/dev/null; then
  echo "tmuxp уже установлен."
else
  echo "Установка tmuxp через Homebrew..."
  brew install tmuxp

  # Проверяем успешность установки
  if brew list tmuxp &>/dev/null; then
    echo "tmuxp успешно установлен."
  else
    echo "Ошибка при установке tmuxp."
    exit 1
  fi
fi
