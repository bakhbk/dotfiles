# Dotfiles

Конфигурационные файлы и полезные скрипты для OS X и Linux.

## Установка

```bash
# Чтобы установить общие конфигурационные файлы на локальном компьютере, выполните следующую команду:
$ ./install.sh
```

## Docker/OrbStack

### Установка OrbStack (рекомендуется для macOS)
```bash
# Установите OrbStack с поддержкой docker-compose или обновите существующую установку
$ ./scripts/install_orbstack.sh
или
$ ./install_orbstack.sh
```

### Удаление Docker Desktop (перед установкой OrbStack)
```bash
# Удалите Docker Desktop чисто
$ ./remove_docker_desktop.sh
```

См. [ORBSTACK.md](ORBSTACK.md) для подробной информации.

Основано на [источниках](https://github.com/alkurbatov/dotfiles)