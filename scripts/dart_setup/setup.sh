#!/bin/zsh

SCRIPT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
source "$SCRIPT_DIR/shared/scripts/setup/common.sh"

FVM_VERSION=${1:-"3.38.9"}

cci "brew" "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
cci "fvm" "curl -fsSL https://fvm.app/install.sh | bash"
cci "protoc" "brew install protobuf"
cci "task" "brew install go-task"
cci "grpcui" "brew install grpcui"
cci "mjml" "brew install mjml"

export PATH="$HOME/.fvm/default/bin:$PATH"
export PATH="$HOME/.pub-cache/bin:$PATH"
source "$SCRIPT_DIR/shared/scripts/setup/flutter_setup.sh"

cci "protoc-gen-dart" "fvm dart pub global activate protoc_plugin 22.5.0"


echo "Версии установленных инструментов:"
ccv "brew версия:" "brew --version"
ccv "protoc версия:" "protoc --version"
ccv "task версия:" "task --version"
ccv "grpcurl версия:" "grpcurl --version"
ccv "fvm версия:" "fvm --version"
ccv "flutter версия:" "fvm flutter --version | head -1"
ccv "dart версия:" "fvm dart --version"
ccv "grpcui версия:" "grpcui --version"
ccv "mjml версия:" "mjml --version"

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
echo "✅ Настройка проекта завершена!"
echo ""
if [ -f Taskfile.yml ]; then
  echo "Доступные команды:"
  task
fi
