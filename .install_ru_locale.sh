#!/bin/bash

set -e # Остановить выполнение при ошибке

# Определение дистрибутива
distro=$(grep ^ID= /etc/os-release | cut -d= -f2 | tr -d '"')

echo "Определён дистрибутив: $distro"

# Проверяем, есть ли уже нужная локаль
if locale -a | grep -q "ru_RU.utf8"; then
  echo "Локаль ru_RU.UTF-8 уже установлена."
  exit 0
fi

echo "Устанавливаем локаль ru_RU.UTF-8..."

case "$distro" in
ubuntu | debian)
  sudo apt update && sudo apt install -y locales
  sudo sed -i 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen
  sudo locale-gen ru_RU.UTF-8
  sudo update-locale LANG=ru_RU.UTF-8
  ;;
arch | manjaro)
  sudo sed -i 's/#ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen
  sudo locale-gen
  echo "LANG=ru_RU.UTF-8" | sudo tee /etc/locale.conf
  ;;
fedora | rhel | centos | rocky | almalinux)
  sudo dnf install -y glibc-langpack-ru
  localectl set-locale LANG=ru_RU.UTF-8
  ;;
*)
  echo "Неизвестный дистрибутив. Пожалуйста, установите локаль вручную."
  exit 1
  ;;
esac

echo "Локаль ru_RU.UTF-8 успешно установлена! Перезагрузите терминал."
