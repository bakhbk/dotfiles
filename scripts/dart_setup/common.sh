#!/bin/zsh

function printhead() {
  clear
  sleep 1
  echo "-----------------------------------"
  echo "Numizma Setup Script"
  echo "-----------------------------------"
  echo ""
  echo "=== $1 ===";
  echo ""
}

cci() {
  (
    printhead "$1..."
    if ! command -v "$1" &>/dev/null; then
      echo "Устанавливаем $1..."
      eval "$2"
      echo "✅ $1 установлен"
    else
      echo "✓ $1 уже установлен"
    fi
  )
}
ccv() {
  (
    printhead "$1..."
    if eval "$2" &>/dev/null; then
      echo "→ $1 $(eval "$2")"
    else
      echo "❌ $1 не найден или произошла ошибка"
    fi
  )
}

add_to_zshrc() {
  local line="$1"
  printhead "Добавляем в ~/.zshrc... $line"
  if ! grep -q "$line" ~/.zshrc 2>/dev/null; then
    echo "$line" >> ~/.zshrc
    echo "✅ Добавлено в ~/.zshrc: $line"
  else
    echo "✓ Уже есть в ~/.zshrc: $line"
  fi
}