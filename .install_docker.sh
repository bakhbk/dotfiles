#!/bin/bash

# Установить Докер
## Обновить индекс пакета apt
sudo apt-get update

## Установите пакеты, чтобы разрешить apt использовать репозиторий через HTTPS
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common

## Добавьте официальный GPG-ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

## Добавьте официальный GPG-ключ Docker
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

## Обновить индекс пакета apt (снова)
sudo apt-get update

## Установите последнюю версию Docker
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Установить Docker Compose 1.29.2
## Загрузите последнюю версию Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

## Сделать Docker Compose исполняемым
sudo chmod +x /usr/local/bin/docker-compose

## Добавить символическую ссылку на исполняемый файл Docker Compose в /usr/bin
sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

## Проверка
sudo docker --version
sudo docker-compose --version

## Добавление пользователя в группу Docker
sudo usermod -aG docker $USER

## Перезагрузка
sudo reboot
