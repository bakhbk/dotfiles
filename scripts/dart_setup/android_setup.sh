#!/bin/zsh

set -euo pipefail  # Exit on error

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]:-$0}")"
source "$SCRIPT_DIR/common.sh"

printhead "Установка Android SDK (Command-Line Tools + компоненты)..."

# === Конфигурация ===
ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
CMD_TOOLS_VERSION="14742923"  # Latest from Google
DOWNLOAD_URL="https://dl.google.com/android/repository/commandlinetools-mac-${CMD_TOOLS_VERSION}_latest.zip"

# === 1. Установка Java 17 (Zulu) ===
echo ""
echo "1️⃣ Проверяю Java 17..."
JAVA_HOME_ZULU="/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home"

if ! java -version 2>&1 | grep -q "17"; then
  echo "   ⏳ Устанавливаю Zulu Java 17..."
  brew install --cask zulu@17
  echo "   ✅ Zulu Java 17 установлен"
fi

export JAVA_HOME="$JAVA_HOME_ZULU"
export PATH="$JAVA_HOME/bin:$PATH"

# === 2. Скачивание Command-Line Tools ===
echo ""
echo "2️⃣ Скачиваю Command-Line Tools (150 MB)..."
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"

TEMP_ZIP="/tmp/android-cmdtools.zip"
rm -f "$TEMP_ZIP"

curl -L --progress-bar -o "$TEMP_ZIP" "$DOWNLOAD_URL"
if [ ! -f "$TEMP_ZIP" ]; then
  echo "❌ Ошибка загрузки"
  exit 1
fi

echo "✅ Скачано, распаковываю..."
# Удаляем старую директорию если она существует
rm -rf "$ANDROID_SDK_ROOT/cmdline-tools/latest"

unzip -q "$TEMP_ZIP" -d "$ANDROID_SDK_ROOT/cmdline-tools"
mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
rm -f "$TEMP_ZIP"

export ANDROID_HOME="$ANDROID_SDK_ROOT"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$PATH"

# === 3. Принятие лицензий ===
echo ""
echo "3️⃣ Принимаю лицензии Android SDK..."
mkdir -p "$ANDROID_SDK_ROOT/licenses"

# Официальные лицензионные хеши от Google
echo -e "\n24333f8a63b6825ea9c5514f83c2829b004d1fee" > "$ANDROID_SDK_ROOT/licenses/android-sdk-license"
echo -e "\n84831b9409646a918e30573bab4c9c91346d8abd" > "$ANDROID_SDK_ROOT/licenses/android-sdk-preview-license"
echo -e "\nd975f751176a0ee3e1cd6218cc07e8c853580b08" > "$ANDROID_SDK_ROOT/licenses/google-android-repo-license"
echo -e "\nec77b39b0b6b7b87b8b4cd0b4bf0e69d793cc3e1" > "$ANDROID_SDK_ROOT/licenses/google-play-services-license"

# === 4. Установка компонентов SDK ===
echo ""
echo "4️⃣ Устанавливаю компоненты SDK..."
SDKMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"

# Update
echo "   ⏳ Инициализирую SDK Manager..."
$SDKMANAGER --update 2>&1 | head -5
echo "      ... (может занять 1-2 минуты)"

# Platform Tools
echo ""
echo "   📦 platform-tools..."
$SDKMANAGER "platform-tools" 2>&1 | grep -E "Downloading|Unzipping|installed" | head -3 || echo "      ⏳ установка..."

# Build Tools  
echo ""
echo "   📦 build-tools;36.0.0..."
$SDKMANAGER "build-tools;36.0.0" 2>&1 | grep -E "Downloading|Unzipping|installed" | head -3 || echo "      ⏳ установка..."

# Android API 36
echo ""
echo "   📦 platforms;android-36..."
$SDKMANAGER "platforms;android-36" 2>&1 | grep -E "Downloading|Unzipping|installed" | head -3 || echo "      ⏳ установка..."

# Emulator
echo ""
echo "   📦 emulator..."
$SDKMANAGER "emulator" 2>&1 | grep -E "Downloading|Unzipping|installed" | head -3 || echo "      ⏳ установка (может занять 2-3 минуты)..."

# System Images
echo ""
echo "   📦 system-images;android-36;google_apis;arm64-v8a (3+ ГБ)..."
$SDKMANAGER "system-images;android-36;google_apis;arm64-v8a" 2>&1 | grep -E "Downloading|Unzipping|installed" | head -5 || echo "      ⏳ загрузка большого файла (может занять 5-10 минут, не прерывайте)..."

echo "✅ Все компоненты установлены"

# === 5. Конфигурация .zshrc ===
echo ""
echo "5️⃣ Добавляю переменные окружения в ~/.zshrc..."
add_to_zshrc "export JAVA_HOME=$JAVA_HOME_ZULU"
add_to_zshrc "export PATH=\"\$JAVA_HOME/bin:\$PATH\""
add_to_zshrc "export ANDROID_HOME=\"\$HOME/Library/Android/sdk\""
add_to_zshrc "export ANDROID_SDK_ROOT=\"\$ANDROID_HOME\""
add_to_zshrc "export PATH=\"\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$PATH\""

# === 6. Принимаем лицензии через flutter ===
echo ""
echo "6️⃣ Принимаю лицензии Flutter (автоматически)..."
yes | fvm flutter doctor --android-licenses >/dev/null 2>&1 || true

# === 7. Проверка установки ===
echo ""
echo "7️⃣ Проверка установки:"
echo "   ANDROID_HOME: $ANDROID_SDK_ROOT"
echo "   JAVA_HOME: $JAVA_HOME"
echo "   Java: $(java -version 2>&1 | head -1)"
echo "   ADB: $($ANDROID_SDK_ROOT/platform-tools/adb --version 2>/dev/null | head -1)"

echo ""
echo "📦 Установленные компоненты:"
$SDKMANAGER --list_installed 2>/dev/null | grep -E "build-tools|platforms|emulator|platform-tools" || echo "   (SDK инициализируется...)"

echo ""
echo "✅ Android SDK полностью установлен!"
echo ""
echo "📌 ОБЯЗАТЕЛЬНО выполните:"
echo "  1. exec zsh              # Перезагрузить shell"
echo "  2. fvm flutter doctor    # Проверить конфигурацию Android"
