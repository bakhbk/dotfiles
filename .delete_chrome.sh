#!/bin/bash

echo "🚨 Полное удаление Google Chrome с Mac"
echo "========================================"

# Завершаем процессы Chrome
echo "1. Завершаем все процессы Chrome..."
pkill -f "Google Chrome"

# Удаляем приложение Chrome
echo "2. Удаляем приложение Chrome..."
sudo rm -rf "/Applications/Google Chrome.app"

# Удаляем файлы пользователя
echo "3. Удаляем пользовательские данные и настройки..."
rm -rf ~/Library/Application\ Support/Google/Chrome/
rm -rf ~/Library/Caches/Google/Chrome/
rm -rf ~/Library/Caches/com.google.Chrome/
rm -rf ~/Library/Preferences/com.google.Chrome.*
rm -rf ~/Library/Saved\ Application\ State/com.google.Chrome.savedState/
rm -rf ~/Library/Google/GoogleSoftwareUpdate/Actives/com.google.Chrome

# Удаляем файлы в системных папках
echo "4. Удаляем системные файлы..."
sudo rm -rf /Library/Application\ Support/Google/Chrome/
sudo rm -rf /Library/Google/Google\ Chrome*
sudo rm -rf /Library/LaunchDaemons/com.google.chrome*
sudo rm -rf /Library/Preferences/com.google.Chrome*

# Удаляем кэш и логи
echo "5. Очищаем кэш и логи..."
rm -rf ~/Library/Logs/Google\ Chrome/
sudo rm -rf /var/log/google-chrome/
sudo rm -rf /var/db/receipts/com.google.Chrome*

# Очищаем корзину (опционально)
echo "6. Очищаем корзину..."
sudo rm -rf ~/.Trash/*Chrome*
sudo rm -rf ~/.Trash/*chrome*

echo "========================================"
echo "✅ Удаление завершено!"
echo ""
echo "Что делать дальше:"
echo "1. Перезагрузите Mac"
echo "2. Скачайте Chrome с официального сайта: https://www.google.com/chrome/"
echo "3. Установите чистую версию"
echo ""
echo "Перезагрузить сейчас? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  sudo reboot
fi
