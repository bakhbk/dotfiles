#!/bin/bash

# Скрипт для управления swap-файлом на Linux серверах
# Использование: sudo ./swap-manager.sh [размер] [действие]
# Пример: sudo ./swap-manager.sh 2G create
#         sudo ./swap-manager.sh show
#         sudo ./swap-manager.sh optimize

set -e  # Прерывать при ошибках

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Ошибка: Этот скрипт должен запускаться с правами root (sudo)${NC}"
        exit 1
    fi
}

# Показать текущее состояние swap
show_status() {
    echo -e "${GREEN}=== Текущее состояние swap ===${NC}"
    echo ""
    
    # Информация о swap
    echo -e "${YELLOW}Активные swap-разделы:${NC}"
    swapon --show
    
    echo ""
    echo -e "${YELLOW}Информация о памяти:${NC}"
    free -h
    
    echo ""
    echo -e "${YELLOW}Настройки ядра:${NC}"
    sysctl vm.swappiness vm.vfs_cache_pressure
    
    echo ""
    echo -e "${YELLOW}Swap в fstab:${NC}"
    grep -i swap /etc/fstab || echo "Не найдено записей о swap в fstab"
}

# Проверить существование swap
check_swap_exists() {
    if swapon --show | grep -q .; then
        return 0  # Swap существует
    else
        return 1  # Swap не существует
    fi
}

# Создать swap-файл
create_swap() {
    local size=$1
    local swapfile="/swapfile"
    
    echo -e "${GREEN}Создание swap-файла размером ${size}...${NC}"
    
    # Проверка существования
    if check_swap_exists; then
        echo -e "${YELLOW}Предупреждение: Swap уже существует. Удалите его сначала.${NC}"
        show_status
        exit 1
    fi
    
    # Проверка свободного места
    local free_space=$(df -h / | awk 'NR==2 {print $4}')
    echo "Свободное место на корневом разделе: $free_space"
    
    # Создание файла
    echo "Создаю swap-файл $swapfile размером $size..."
    
    if command -v fallocate &> /dev/null; then
        fallocate -l "$size" "$swapfile"
    else
        # Альтернативный метод для старых систем
        local size_mb=$(echo "$size" | sed 's/[^0-9]*//g')
        if [[ "$size" == *"G"* ]]; then
            size_mb=$((size_mb * 1024))
        fi
        dd if=/dev/zero of="$swapfile" bs=1M count="$size_mb" status=progress
    fi
    
    # Установка прав
    chmod 600 "$swapfile"
    
    # Форматирование как swap
    mkswap "$swapfile"
    
    # Активация
    swapon "$swapfile"
    
    # Добавление в fstab
    if ! grep -q "$swapfile" /etc/fstab; then
        echo "$swapfile none swap sw 0 0" >> /etc/fstab
        echo "Добавлено в /etc/fstab"
    fi
    
    echo -e "${GREEN}Swap-файл успешно создан и активирован!${NC}"
}

# Удалить swap-файл
remove_swap() {
    local swapfile="/swapfile"
    
    echo -e "${YELLOW}Удаление swap-файла...${NC}"
    
    # Деактивация swap
    if check_swap_exists; then
        swapoff -a
    fi
    
    # Удаление из fstab
    sed -i '\|'"$swapfile"'|d' /etc/fstab
    
    # Удаление файла
    if [[ -f "$swapfile" ]]; then
        rm -f "$swapfile"
        echo "Файл $swapfile удален"
    fi
    
    echo -e "${GREEN}Swap успешно удален!${NC}"
}

# Оптимизировать настройки swap
optimize_swap() {
    echo -e "${GREEN}Оптимизация настроек swap...${NC}"
    
    # Рекомендуемые настройки для сервера
    local sysctl_file="/etc/sysctl.conf"
    local backup_file="${sysctl_file}.bak.$(date +%Y%m%d)"
    
    # Создаем backup
    cp "$sysctl_file" "$backup_file"
    echo "Создан backup: $backup_file"
    
    # Обновляем или добавляем параметры
    declare -A params=(
        ["vm.swappiness"]="10"
        ["vm.vfs_cache_pressure"]="50"
        ["vm.dirty_ratio"]="10"
        ["vm.dirty_background_ratio"]="5"
    )
    
    for param in "${!params[@]}"; do
        local value="${params[$param]}"
        
        if grep -q "^${param}=" "$sysctl_file"; then
            # Параметр существует, обновляем
            sed -i "s/^${param}=.*/${param}=${value}/" "$sysctl_file"
            echo "Обновлен: $param=$value"
        elif grep -q "^#${param}=" "$sysctl_file"; then
            # Закомментированный параметр, раскомментируем
            sed -i "s/^#${param}=.*/${param}=${value}/" "$sysctl_file"
            echo "Раскомментирован: $param=$value"
        else
            # Параметр не существует, добавляем
            echo "" >> "$sysctl_file"
            echo "# Optimized by swap-manager" >> "$sysctl_file"
            echo "$param=$value" >> "$sysctl_file"
            echo "Добавлен: $param=$value"
        fi
    done
    
    # Применяем настройки
    sysctl -p
    
    echo -e "${GREEN}Настройки оптимизированы!${NC}"
    
    # Устанавливаем ранний OOM killer если нужно
    install_earlyoom
}

# Установить earlyoom
install_earlyoom() {
    if command -v apt-get &> /dev/null; then
        if ! dpkg -l | grep -q earlyoom; then
            echo "Установка earlyoom (Out Of Memory killer)..."
            apt-get update
            apt-get install -y earlyoom
            systemctl enable --now earlyoom
        fi
    elif command -v yum &> /dev/null; then
        if ! rpm -q earlyoom &> /dev/null; then
            echo "Установка earlyoom..."
            yum install -y epel-release
            yum install -y earlyoom
            systemctl enable --now earlyoom
        fi
    fi
}

# Показать справку
show_help() {
    echo -e "${GREEN}=== Менеджер swap-файлов ===${NC}"
    echo ""
    echo "Использование:"
    echo "  $0 [размер] [действие]"
    echo "  $0 [действие]"
    echo ""
    echo "Действия:"
    echo "  create [размер]   - Создать swap-файл (по умолчанию 2G)"
    echo "  remove            - Удалить swap-файл"
    echo "  show              - Показать текущее состояние"
    echo "  optimize          - Оптимизировать настройки"
    echo "  check             - Проверить, существует ли swap"
    echo "  help              - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 create 2G      # Создать swap 2 ГБ"
    echo "  $0 create 4G      # Создать swap 4 ГБ"
    echo "  $0 show           # Показать информацию"
    echo "  $0 remove         # Удалить swap"
    echo "  $0 optimize       # Оптимизировать настройки"
    echo ""
    echo "Размеры:"
    echo "  Используйте суффиксы: M (мегабайты), G (гигабайты)"
    echo "  Примеры: 512M, 1G, 2G, 4G"
}

# Основная функция
main() {
    check_root
    
    local action=${1:-"show"}
    local size=${2:-"2G"}
    
    case "$action" in
        "create")
            create_swap "$size"
            show_status
            ;;
        "remove")
            remove_swap
            show_status
            ;;
        "show"|"status")
            show_status
            ;;
        "optimize"|"tune")
            optimize_swap
            show_status
            ;;
        "check")
            if check_swap_exists; then
                echo -e "${GREEN}Swap существует${NC}"
                swapon --show
            else
                echo -e "${YELLOW}Swap не существует${NC}"
            fi
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            # Если первый аргумент выглядит как размер
            if [[ "$action" =~ ^[0-9]+[MG]$ ]]; then
                create_swap "$action"
                show_status
            else
                echo -e "${RED}Неизвестное действие: $action${NC}"
                echo ""
                show_help
                exit 1
            fi
            ;;
    esac
}

# Запуск скрипта
main "$@"