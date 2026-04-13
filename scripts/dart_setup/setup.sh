#!/bin/zsh

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]:-$0}")"
source "$SCRIPT_DIR/common.sh"

FVM_VERSION=${1:-"3.38.9"}

cci "brew" "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
cci "fvm" "curl -fsSL https://fvm.app/install.sh | bash"
cci "protoc" "brew install protobuf"
cci "task" "brew install go-task"
cci "grpcui" "brew install grpcui"
cci "mjml" "brew install mjml"

export PATH="$HOME/.fvm/default/bin:$PATH"
export PATH="$HOME/.pub-cache/bin:$PATH"

# === Установляем глобальную FVM версию ===
printhead "Устанавливаем Flutter версию $FVM_VERSION..."
fvm install "$FVM_VERSION" >/dev/null 2>&1 || true
fvm use "$FVM_VERSION" --force -s

# Android SDK Setup
source "$SCRIPT_DIR/android_setup.sh"

# Flutter Setup
source "$SCRIPT_DIR/flutter_setup.sh"

cci "protoc-gen-dart" "fvm dart pub global activate protoc_plugin 22.5.0"
cci "flutterfire_cli" "fvm dart pub global activate flutterfire_cli"


printhead "Versions:"
ccv "brew version:" "brew --version"
ccv "protoc version:" "protoc --version"
ccv "task version:" "task --version"
ccv "grpcurl version:" "grpcurl --version"
ccv "fvm version:" "fvm --version"
ccv "flutter version:" "fvm flutter --version | head -1"
ccv "dart version:" "fvm dart --version"
ccv "grpcui version:" "grpcui --version"
ccv "mjml version:" "mjml --version"
ccv "protoc-gen-dart version:" "fvm dart pub global list | grep protoc_plugin"
ccv "flutterfire version:" "flutterfire --version"

# Проверяем protoc-gen-dart
if command -v protoc-gen-dart &>/dev/null; then
  echo "✓ protoc-gen-dart доступен в PATH"
else
  echo "❌ protoc-gen-dart не найден в PATH"
  add_to_zshrc 'export PATH="$HOME/.pub-cache/bin:$PATH"'
  add_to_zshrc 'export PATH="$HOME/.fvm/default/bin:$PATH"'
  echo ""
  echo "Перезапустите терминал или выполните:"
  echo "source ~/.zshrc"
fi

echo ""
echo "✅ Project setup completed!"
echo ""
if [ -f Taskfile.yml ]; then
  echo "Available commands:"
  task
fi
