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

  # Определяем команду для выполнения
  COMMAND=${1:-"pwd"} # Если аргумент не передан, используем "pwd"

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

  # Добавляем команды для каждой папки в текущей директории
  for dir in $(ls -d "$BASE_DIR"/*/); do
    dir_name=$(basename "$dir")
    echo "      - cd $dir_name && $COMMAND" >>"$YAML_FILE"
  done

  echo "YAML-файл успешно создан: $YAML_FILE"
  echo "Запустите tmuxp load $SESSION_NAME для загрузки сессии."
  tmuxp load "$SESSION_NAME"
}
