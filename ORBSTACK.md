# Установка OrbStack

Скрипт `.install_orbstack.sh` автоматически устанавливает или обновляет OrbStack на macOS.

## Особенности

- ✅ Автоматическая установка/обновление OrbStack через Homebrew
- ✅ Поддержка современной команды `docker compose` (без дефиса)
- ✅ Автоматическая установка Homebrew если отсутствует
- ✅ Корректная остановка и запуск OrbStack при обновлении
- ✅ Тестирование установки с помощью hello-world
- ✅ Проверка работоспособности docker compose

## Использование

```bash
# Запуск скрипта установки
./install_orbstack.sh
```

## Доступные команды после установки

### Docker Compose (современный синтаксис)
```bash
docker compose up -d
docker compose down
docker compose build
docker compose logs
```

### Алиасы (добавлены в .zsh_aliases)
```bash
dc           # docker compose
dcu          # docker compose up
dcd          # docker compose down
dcb          # docker compose build
dcl          # docker compose logs
dcp          # docker compose pull
dcr          # docker compose restart
dce          # docker compose exec

d            # docker
di           # docker images
dps          # docker ps
dpsa         # docker ps -a
```

## Преимущества OrbStack

- 🚀 Быстрее Docker Desktop
- 💾 Меньше потребление ресурсов
- 🔧 Лучшая интеграция с macOS
- 📱 Современный UI
- ⚡ Быстрый запуск контейнеров
- 🔄 Поддержка Linux виртуальных машин

## Требования

- macOS (Intel или Apple Silicon)
- Homebrew (устанавливается автоматически если отсутствует)
