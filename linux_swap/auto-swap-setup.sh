#!/bin/bash
# Автоматическая настройка swap если его нет

MIN_RAM_MB=2048  # Минимум 2ГБ RAM для создания swap
SWAP_SIZE="2G"   # Размер swap по умолчанию

# Проверяем общий объем RAM
TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')

echo "Общий объем RAM: ${TOTAL_RAM}MB"

if [ "$TOTAL_RAM" -lt "$MIN_RAM_MB" ]; then
    echo "Мало RAM (${TOTAL_RAM}MB < ${MIN_RAM_MB}MB), рекомендуется создать swap"
    
    if ! sudo ./swap-manager.sh check; then
        echo "Создаю swap ${SWAP_SIZE}..."
        sudo ./swap-manager.sh create "$SWAP_SIZE"
        sudo ./swap-manager.sh optimize
    else
        echo "Swap уже существует"
    fi
else
    echo "RAM достаточно, swap не требуется"
fi

# Показать итоговое состояние
sudo ./swap-manager.sh show