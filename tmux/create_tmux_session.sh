#!/bin/bash

ctmux() {
  # Получаем путь к текущей директории
  BASE_DIR=$(pwd)

  # Получаем имя текущей папки (без полного пути)
  SESSION_NAME=$(basename "$BASE_DIR")

  # Создаем каталог ~/.tmuxp, если он не существует
  mkdir -p ~/.tmuxp

  # Путь к YAML-файлу
  YAML_FILE=~/.tmuxp/$SESSION_NAME.yaml

  # Удаляем предыдущий YAML-файл, если он существует
  if [[ -f "$YAML_FILE" ]]; then
    echo "Удаление предыдущего YAML-файла: $YAML_FILE"
    rm "$YAML_FILE"
  fi

  # Определяем команду для выполнения (последний аргумент)
  # Если аргументы содержат папки, то последний аргумент - команда
  COMMAND="pwd" # значение по умолчанию
  FOLDERS=()
  
  # Разделяем аргументы на папки и команду
  for arg in "$@"; do
    if [[ -d "$arg" ]]; then
      FOLDERS+=("$arg")
    else
      COMMAND="$arg"
    fi
  done

  # Если не переданы папки, используем все подпапки в текущей директории
  if [[ ${#FOLDERS[@]} -eq 0 ]]; then
    for dir in $(ls -d "$BASE_DIR"/*/); do
      FOLDERS+=("$(basename "$dir")")
    done
  fi

  # Создаем новый YAML-файл
  cat <<EOF >"$YAML_FILE"
session_name: $SESSION_NAME
windows:
  - window_name: $SESSION_NAME
    layout: tiled
    shell_command_before:
      - cd $BASE_DIR
    panes:
EOF

  # Добавляем команды для каждой указанной папки
  for folder in "${FOLDERS[@]}"; do
    echo "      - cd $folder && $COMMAND" >>"$YAML_FILE"
  done

  echo "YAML-файл успешно создан: $YAML_FILE"
  echo "Запустите tmuxp load $SESSION_NAME для загрузки сессии."
  tmuxp load "$SESSION_NAME"
}