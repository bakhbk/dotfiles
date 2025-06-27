#!/bin/bash

# Скрипт установки/обновления OrbStack для macOS
# OrbStack - современная замена Docker Desktop с поддержкой docker compose

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверяем, что это macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    log_error "OrbStack поддерживается только на macOS"
    exit 1
fi

# Проверяем наличие Homebrew
if ! command -v brew &> /dev/null; then
    log_warning "Homebrew не найден. Устанавливаем Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Добавляем Homebrew в PATH для Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# Функция для проверки, запущен ли OrbStack
is_orbstack_running() {
    pgrep -f "OrbStack" > /dev/null 2>&1
}

# Функция для остановки OrbStack
stop_orbstack() {
    if is_orbstack_running; then
        log_info "Останавливаем OrbStack..."
        osascript -e 'quit app "OrbStack"' 2>/dev/null || true
        sleep 3
        
        # Принудительная остановка если не помогло
        if is_orbstack_running; then
            log_warning "Принудительно останавливаем OrbStack..."
            pkill -f "OrbStack" 2>/dev/null || true
            sleep 2
        fi
    fi
}

# Функция для запуска OrbStack
start_orbstack() {
    log_info "Запускаем OrbStack..."
    open -a OrbStack
    
    # Ждем запуска
    local max_attempts=30
    local attempt=0
    
    while ! command -v docker &> /dev/null && [ $attempt -lt $max_attempts ]; do
        sleep 2
        ((attempt++))
        echo -n "."
    done
    echo
    
    if command -v docker &> /dev/null; then
        log_success "OrbStack успешно запущен"
    else
        log_warning "OrbStack может быть еще не готов. Подождите немного..."
    fi
}

# Проверяем, установлен ли уже OrbStack
if brew list --cask orbstack &> /dev/null; then
    log_info "OrbStack уже установлен. Проверяем обновления..."
    
    # Останавливаем OrbStack перед обновлением
    stop_orbstack
    
    # Обновляем OrbStack
    if brew upgrade --cask orbstack; then
        log_success "OrbStack успешно обновлен"
    else
        log_warning "Обновление не требуется или произошла ошибка"
    fi
else
    log_info "Устанавливаем OrbStack..."
    
    # Устанавливаем OrbStack
    if brew install --cask orbstack; then
        log_success "OrbStack успешно установлен"
    else
        log_error "Ошибка при установке OrbStack"
        exit 1
    fi
fi

# Запускаем OrbStack
start_orbstack

# Проверяем установку и настройку docker compose
log_info "Проверяем настройку Docker..."

# Ждем, пока docker станет доступен
max_wait=60
wait_time=0
while ! docker info &> /dev/null && [ $wait_time -lt $max_wait ]; do
    sleep 2
    wait_time=$((wait_time + 2))
    echo -n "."
done
echo

if ! docker info &> /dev/null; then
    log_error "Docker не запустился в течение ${max_wait} секунд"
    log_info "Попробуйте запустить OrbStack вручную и повторить проверку"
    exit 1
fi

# Проверяем версии
log_info "Проверяем версии..."
echo
docker --version
echo

# Проверяем поддержку docker compose (новый синтаксис)
if docker compose version &> /dev/null; then
    log_success "✅ Команда 'docker compose' работает корректно"
    docker compose version
else
    log_warning "⚠️  Команда 'docker compose' не работает"
fi

echo

# Проверяем поддержку старого синтаксиса docker-compose (если нужно)
if command -v docker-compose &> /dev/null; then
    log_info "📝 Также доступна команда 'docker-compose' (старый синтаксис)"
    docker-compose --version
else
    log_info "💡 Используйте команду 'docker compose' (без дефиса) - это современный синтаксис"
fi

echo

# Тестируем Docker
log_info "Тестируем Docker..."
if docker run --rm hello-world &> /dev/null; then
    log_success "✅ Docker работает корректно!"
else
    log_error "❌ Ошибка при тестировании Docker"
    exit 1
fi

# Тестируем docker compose
log_info "Тестируем docker compose..."

# Создаем временный docker-compose.yml для теста
temp_dir=$(mktemp -d)
cat > "$temp_dir/docker-compose.yml" << 'EOF'
version: '3.8'
services:
  test:
    image: alpine:latest
    command: echo "Docker Compose works!"
EOF

cd "$temp_dir"
if docker compose up --quiet-pull 2>/dev/null; then
    log_success "✅ Docker Compose работает корректно!"
else
    log_error "❌ Ошибка при тестировании Docker Compose"
fi

# Очищаем временные файлы
cd - > /dev/null
rm -rf "$temp_dir"

echo
log_success "🎉 Установка OrbStack завершена!"
echo
log_info "📋 Доступные команды:"
echo "   • docker --version"
echo "   • docker compose version"
echo "   • docker run hello-world"
echo "   • docker compose up -d"
echo
log_info "💡 Используйте 'docker compose' (с пробелом) вместо 'docker-compose' (с дефисом)"
log_info "🔧 OrbStack GUI доступен в Applications или через Spotlight"
