#!/bin/zsh

function printhead() {
  clear
  echo "-----------------------------------"
  echo " Setup Script"
  echo "-----------------------------------"
  echo ""
  echo "=== $1 ===";
  echo ""
  sleep 2
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
    if eval "$2" &>/dev/null; then
      echo "→ $1 $(eval "$2")"
    else
      echo "❌ $1 не найден или произошла ошибка"
    fi
  )
}

get_latest_stable_fvm() {
  local ver
  ver=$(fvm releases -c stable 2>/dev/null | \
        sed 's/\x1b\[[0-9;]*m//g' | \
        grep 'stable' | tail -1 | \
        awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.[0-9]+\.[0-9]+$/) print $i}')
  echo "${ver:-3.44.5}"
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
