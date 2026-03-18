#!/bin/bash

echo "🚀 Начинаю полную очистку Android Studio и связанных кешей..."

# 1. Удаление самого приложения
sudo rm -rf /Applications/Android\ Studio.app

# 2. Удаление конфигураций и настроек (Library/Application Support)
# В новых версиях (в т.ч. Panda 2) это папка Google/AndroidStudio2025.3
rm -rf ~/Library/Application\ Support/Google/AndroidStudio*
rm -rf ~/Library/Application\ Support/AndroidStudio*

# 3. Удаление кешей
rm -rf ~/Library/Caches/Google/AndroidStudio*
rm -rf ~/Library/Caches/AndroidStudio*

# 4. Удаление логов
rm -rf ~/Library/Logs/Google/AndroidStudio*

# 5. Удаление плагинов и данных расширений
rm -rf ~/Library/Preferences/AndroidStudio*
rm -rf ~/Library/Preferences/com.google.android.studio.plist

# 6. ОЧИСТКА ГЛОБАЛЬНЫХ НАСТРОЕК (Важно для M1)
# Это сбросит настройки ADB и эмуляторов, которые могут блокировать тапы
rm -rf ~/.android

# 7. Очистка Gradle (опционально, но рекомендуется при багах сборки)
# Внимание: это заставит студию заново качать зависимости в проектах
# rm -rf ~/.gradle

echo "✅ Очистка завершена! Теперь установите стабильную версию (Ladybug/Koala)."
echo "⚠️ После установки не забудьте заново включить USB Debugging на телефоне."
