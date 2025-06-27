#!/bin/bash

# Скрипт для обслуживания истории zsh
# Использование: ./history_maintenance.sh [опция]

set -euo pipefail

HISTFILE="${HOME}/.dotfiles/.zsh_history"
BACKUP_DIR="${HOME}/.dotfiles/history_backups"
MAX_BACKUPS=10

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Создание резервной копии
backup_history() {
    print_info "Создание резервной копии истории..."
    
    if [[ ! -f "$HISTFILE" ]]; then
        print_error "Файл истории не найден: $HISTFILE"
        return 1
    fi
    
    mkdir -p "$BACKUP_DIR"
    local backup_file="$BACKUP_DIR/zsh_history_$(date +%Y%m%d_%H%M%S).bak"
    
    cp "$HISTFILE" "$backup_file"
    print_success "Резервная копия создана: $backup_file"
    
    # Удаляем старые резервные копии
    cleanup_old_backups
}

# Очистка старых резервных копий
cleanup_old_backups() {
    print_info "Очистка старых резервных копий..."
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        return 0
    fi
    
    local backup_count=$(ls -1 "$BACKUP_DIR"/zsh_history_*.bak 2>/dev/null | wc -l)
    
    if [[ $backup_count -gt $MAX_BACKUPS ]]; then
        local files_to_delete=$((backup_count - MAX_BACKUPS))
        ls -1t "$BACKUP_DIR"/zsh_history_*.bak | tail -n "$files_to_delete" | xargs rm -f
        print_info "Удалено $files_to_delete старых резервных копий"
    fi
}

# Дедупликация истории
deduplicate_history() {
    print_info "Дедупликация истории..."
    
    if [[ ! -f "$HISTFILE" ]]; then
        print_error "Файл истории не найден: $HISTFILE"
        return 1
    fi
    
    # Создаем резервную копию перед дедупликацией
    backup_history
    
    # Временный файл для обработки
    local temp_file=$(mktemp)
    
    # Дедупликация с сохранением порядка (последнее вхождение)
    tac "$HISTFILE" | awk '!seen[$0]++' | tac > "$temp_file"
    
    # Подсчет результатов
    local original_lines=$(wc -l < "$HISTFILE")
    local new_lines=$(wc -l < "$temp_file")
    local removed_lines=$((original_lines - new_lines))
    
    # Замена оригинального файла
    mv "$temp_file" "$HISTFILE"
    
    print_success "Дедупликация завершена: удалено $removed_lines дубликатов из $original_lines команд"
}

# Очистка истории
clean_history() {
    print_warning "Это действие полностью очистит историю команд!"
    read -p "Вы уверены? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        backup_history
        echo "" > "$HISTFILE"
        print_success "История очищена"
    else
        print_info "Операция отменена"
    fi
}

# Анализ истории
analyze_history() {
    print_info "Анализ истории команд..."
    
    if [[ ! -f "$HISTFILE" ]]; then
        print_error "Файл истории не найден: $HISTFILE"
        return 1
    fi
    
    local total_commands=$(wc -l < "$HISTFILE")
    print_info "Общее количество команд: $total_commands"
    
    echo ""
    print_info "Топ-10 самых используемых команд:"
    awk '{print $1}' "$HISTFILE" | sort | uniq -c | sort -nr | head -10
    
    echo ""
    print_info "Размер файла истории:"
    ls -lh "$HISTFILE" | awk '{print $5}'
}

# Показать статистику
show_stats() {
    print_info "Статистика истории команд:"
    
    if [[ ! -f "$HISTFILE" ]]; then
        print_error "Файл истории не найден: $HISTFILE"
        return 1
    fi
    
    echo "📁 Файл истории: $HISTFILE"
    echo "📊 Общее количество команд: $(wc -l < "$HISTFILE")"
    echo "💾 Размер файла: $(ls -lh "$HISTFILE" | awk '{print $5}')"
    echo "📅 Последнее изменение: $(ls -l "$HISTFILE" | awk '{print $6, $7, $8}')"
    
    if [[ -d "$BACKUP_DIR" ]]; then
        local backup_count=$(ls -1 "$BACKUP_DIR"/zsh_history_*.bak 2>/dev/null | wc -l)
        echo "🔄 Количество резервных копий: $backup_count"
    fi
}

# Показать помощь
show_help() {
    echo "Скрипт обслуживания истории zsh"
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  backup      Создать резервную копию истории"
    echo "  dedupe      Удалить дубликаты из истории"
    echo "  clean       Полностью очистить историю"
    echo "  analyze     Проанализировать историю"
    echo "  stats       Показать статистику"
    echo "  help        Показать эту справку"
    echo ""
    echo "Если команда не указана, будет выполнена дедупликация."
}

# Основная логика
main() {
    case "${1:-dedupe}" in
        backup)
            backup_history
            ;;
        dedupe)
            deduplicate_history
            ;;
        clean)
            clean_history
            ;;
        analyze)
            analyze_history
            ;;
        stats)
            show_stats
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Неизвестная команда: $1"
            show_help
            exit 1
            ;;
    esac
}

# Запуск скрипта
main "$@"
