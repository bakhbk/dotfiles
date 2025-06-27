#!/bin/bash

# Убедимся, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then
  echo "Пожалуйста, запустите скрипт от имени root."
  exit 1
fi

# Обновление системы
echo "Обновление системы..."
apt update && apt upgrade -y

# Установка зависимостей
echo "Установка зависимостей..."
apt install -y wget dpkg

# Скачивание RustDesk
echo "Скачивание RustDesk..."
wget https://github.com/rustdesk/rustdesk/releases/download/1.1.9/rustdesk-1.1.9-x86_64.deb -O /tmp/rustdesk.deb

# Установка RustDesk
echo "Установка RustDesk..."
dpkg -i /tmp/rustdesk.deb || apt-get install -f -y

# Запрос пароля для неконтролируемого доступа
read -sp "Введите пароль для неконтролируемого доступа: " RUSTDESK_PASSWORD
echo # Переход на новую строку после ввода пароля

# Установка пароля для RustDesk
echo "Настройка RustDesk..."
rustdesk --set-password "$RUSTDESK_PASSWORD"

# Создание systemd-юнита для автозапуска
echo "Создание systemd-юнита..."
cat <<EOF >/etc/systemd/system/rustdesk.service
[Unit]
Description=RustDesk Remote Desktop Service
After=network.target

[Service]
User=root
ExecStart=/usr/bin/rustdesk --service
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd и запуск RustDesk
echo "Запуск RustDesk..."
systemctl daemon-reload
systemctl enable rustdesk
systemctl start rustdesk

# Даём RustDesk время на запуск
echo "Ожидание запуска RustDesk..."
sleep 5

# Получение RustDesk ID
RUSTDESK_ID=$(rustdesk --get-id)
if [ -z "$RUSTDESK_ID" ]; then
  echo "Ошибка: Не удалось получить RustDesk ID. Попробуйте запустить RustDesk вручную."
else
  echo "Ваш RustDesk ID: $RUSTDESK_ID"
fi

# Очистка временных файлов
echo "Очистка временных файлов..."
rm -f /tmp/rustdesk.deb

echo "Установка RustDesk завершена!"
if [ -n "$RUSTDESK_ID" ]; then
  echo "Ваш RustDesk ID: $RUSTDESK_ID"
fi
echo "Пароль для неконтролируемого доступа: $RUSTDESK_PASSWORD"
