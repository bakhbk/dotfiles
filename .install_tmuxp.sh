#!/bin/bash

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
