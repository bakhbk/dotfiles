# Flutter Android SDK Setup

## ✅ Реализовано

### 1. **android_setup.sh** – Инициализация Android окружения
- Установка **OpenJDK 17** (необходимо для Android)
- Экспорт переменных окружения:
  - `ANDROID_HOME` → `$HOME/Library/Android/sdk`
  - `ANDROID_SDK_ROOT` → `$ANDROID_HOME`
  - `JAVA_HOME` → версия 17
  - `PATH` → добавление tools, platform-tools, emulator
- Проверка и вывод версий Java
- Инструкции для установки Android Studio (опционально)

### 2. **setup.sh** – Главный скрипт инициализации
- Установка зависимостей: Brew, FVM, Protoc, Task, GrpcUI, MJML
- **Критично**: Явная установка Flutter версии 3.38.9 через FVM `fvm use --force -s`
- Вызов `android_setup.sh` перед Flutter setup
- Вызов `flutter_setup.sh` для проектов с .fvmrc
- Установка глобальных Dart инструментов: protoc-gen-dart, flutterfire_cli
- Вывод всех версий для проверки

### 3. **flutter_setup.sh** – Конфигурация Flutter проектов
- Настройка проектов с `.fvmrc` файлами асинхронно
- `fvm use --force -s $FVM_VERSION` – установка версии в каждом проекте
- Отключение analytics
- Clean build и pub get для всех проектов

## 🚀 Использование

### Полная инициализация:
```bash
cd /Users/b/dotfiles/scripts/dart_setup
./setup.sh 3.38.9
```

### Или отдельно по частям:
```bash
# Только Android SDK
./android_setup.sh

# Только Flutter проекты
./flutter_setup.sh
```

### Параметры:
- `FVM_VERSION` – версия Flutter (default: 3.38.9)
```bash
./setup.sh 3.24.0  # другая версия
```

## 📋 Требования после выполнения

### Обязательные шаги:
1. **Перезапустите терминал или выполните:**
   ```bash
   source ~/.zshrc
   ```

2. **Проверьте установку:**
   ```bash
   fvm flutter doctor
   ```

3. **Для эмулятора (опционально):**
   ```bash
   brew install --cask android-studio
   ```
   Затем в Android Studio: Tools → Device Manager → Create Device

## ✨ Особенности

| Компонент | Статус | Примечание |
|-----------|--------|-----------|
| **Android SDK** | ✅ | Через переменные окружения |
| **Java 17** | ✅ | Установлено через Brew |
| **Flutter 3.38.9** | ✅ | Через FVM |
| **ADB** | ℹ️ | Придет с Android Studio (опционально) |
| **Эмулятор** | ℹ️ | Скачивается через Android Studio |
| **Dart tools** | ✅ | protoc-gen-dart, flutterfire_cli |

## 🔍 Проверка статуса

```bash
# Flutter и Dart
fvm flutter --version
fvm dart --version

# Android
echo $ANDROID_HOME
echo $JAVA_HOME

# Java
java -version

# Все статусы
fvm flutter doctor
```

## 📝 Если что-то не работает

### Flutter не найден:
```bash
# Установите версию явно
fvm install 3.38.9
fvm use 3.38.9 --force -s

# Или перезагрузите переменные
exec zsh
```

### Android SDK не найден:
```bash
# Проверьте переменные
echo $ANDROID_HOME
ls ~/Library/Android/sdk/

# При необходимости установите Android Studio
brew install --cask android-studio
```

### ADB не найден:
```bash
# Установится с Android Studio или скачайте отдельно
# Проверьте PATH
echo $PATH | grep -i android
```

## 🎯 Результат для разработки:

После выполнения рекомендуется:
1. ✅ Запускать эмулятор можно через Android Studio
2. ✅ `flutter build apk` будет работать корректно
3. ✅ `flutter run` на устройстве/эмуляторе будет работать
4. ✅ `fvm flutter doctor` должен показать зелено-желтый статус
