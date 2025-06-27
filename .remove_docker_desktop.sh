#!/bin/bash

# Скрипт для удаления Docker Desktop перед установкой OrbStack
# OrbStack - более быстрая и легкая альтернатива Docker Desktop

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    log_error "Этот скрипт предназначен только для macOS"
    exit 1
fi

log_info "🗑️  Удаление Docker Desktop..."

# Останавливаем Docker Desktop если запущен
if pgrep -f "Docker Desktop" > /dev/null 2>&1; then
    log_info "Останавливаем Docker Desktop..."
    osascript -e 'quit app "Docker"' 2>/dev/null || true
    sleep 3
    
    # Принудительная остановка если не помогло
    if pgrep -f "Docker Desktop" > /dev/null 2>&1; then
        log_warning "Принудительно останавливаем Docker Desktop..."
        pkill -f "Docker" 2>/dev/null || true
        sleep 2
    fi
fi

# Удаляем Docker Desktop через Homebrew если установлен
if brew list --cask docker &> /dev/null; then
    log_info "Удаляем Docker Desktop через Homebrew..."
    brew uninstall --cask docker || log_warning "Не удалось удалить Docker Desktop через Homebrew"
fi

# Удаляем приложение Docker
if [ -d "/Applications/Docker.app" ]; then
    log_info "Удаляем Docker.app из Applications..."
    rm -rf "/Applications/Docker.app"
fi

# Удаляем пользовательские данные Docker
docker_dirs=(
    "$HOME/.docker"
    "$HOME/Library/Application Support/Docker Desktop"
    "$HOME/Library/Preferences/com.docker.docker.plist"
    "$HOME/Library/Saved Application State/com.electron.docker-frontend.savedState"
    "$HOME/Library/Group Containers/group.com.docker"
    "$HOME/Library/Containers/com.docker.docker"
    "$HOME/Library/Containers/com.docker.helper"
    "/Library/LaunchDaemons/com.docker.vmnetd.plist"
    "/Library/PrivilegedHelperTools/com.docker.vmnetd"
    "/var/lib/docker"
)

for dir in "${docker_dirs[@]}"; do
    if [ -e "$dir" ]; then
        log_info "Удаляем $dir..."
        rm -rf "$dir" 2>/dev/null || sudo rm -rf "$dir" 2>/dev/null || log_warning "Не удалось удалить $dir"
    fi
done

# Удаляем Docker-контексты
if command -v docker &> /dev/null; then
    log_info "Очищаем Docker контексты..."
    docker context ls -q | grep -v default | xargs -r docker context rm 2>/dev/null || true
fi

# Удаляем Hyperkit и другие компоненты Docker Desktop
if [ -f "/usr/local/bin/hyperkit" ]; then
    log_info "Удаляем hyperkit..."
    sudo rm -f "/usr/local/bin/hyperkit"
fi

# Удаляем символические ссылки
links_to_remove=(
    "/usr/local/bin/docker"
    "/usr/local/bin/docker-compose"
    "/usr/local/bin/docker-credential-desktop"
    "/usr/local/bin/docker-credential-ecr-login"
    "/usr/local/bin/docker-credential-osxkeychain"
)

for link in "${links_to_remove[@]}"; do
    if [ -L "$link" ]; then
        log_info "Удаляем символическую ссылку $link..."
        rm -f "$link"
    fi
done

log_success "✅ Docker Desktop успешно удален!"
echo
log_info "💡 Теперь можно установить OrbStack:"
log_info "   ./install_orbstack.sh"
echo
log_warning "⚠️  После удаления Docker Desktop вам может потребоваться:"
log_warning "   1. Перезагрузить терминал"
log_warning "   2. Проверить переменные окружения PATH"
log_warning "   3. Удалить старые Docker образы и контейнеры"
