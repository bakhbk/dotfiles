#!/bin/bash

# Список популярных моделей для программирования
MODELS=(
  "deepseek-coder:6.7b"
  "deepseek-coder:33b"
  "codellama:7b"
  "codellama:13b"
  "starcoder2:15b"
  "llama3:8b"
  "codegemma:7b"
)

echo "Выберите модель для скачивания:"
select MODEL in "${MODELS[@]}" "Выйти"; do
  case $MODEL in
  "Выйти")
    echo "Выход..."
    exit 0
    ;;
  *)
    if [[ -n "$MODEL" ]]; then
      echo "Скачиваем: $MODEL"
      ollama pull "$MODEL"
      break
    else
      echo "Неверный выбор. Попробуйте еще раз."
    fi
    ;;
  esac
done
