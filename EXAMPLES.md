# Примеры использования улучшенных dotfiles

## 🎯 Быстрый старт

После установки попробуйте эти команды:

```bash
# Перезагрузите терминал или выполните
source ~/.zshrc

# Проверьте установку
~/.dotfiles/scripts/verify_installation.sh
```

## 📊 Работа с историей

### Поиск в истории
```bash
# Fuzzy поиск с помощью fzf
fh

# Поиск конкретной команды
hgrep docker

# Показать статистику
hs

# Показать последние 20 команд
lc 20
```

### Выполнение команд из истории
```bash
# Интерактивный выбор и выполнение
efh

# Выполнить последнюю команду с sudo
sl

# Повторить команду из истории с изменениями
# 1. Найдите команду: fh
# 2. Отредактируйте в командной строке
# 3. Выполните
```

### Управление историей
```bash
# Показать статистику файла истории
~/.dotfiles/scripts/history_maintenance.sh stats

# Удалить дубликаты
~/.dotfiles/scripts/history_maintenance.sh dedupe

# Проанализировать самые используемые команды
~/.dotfiles/scripts/history_maintenance.sh analyze

# Создать резервную копию
~/.dotfiles/scripts/history_maintenance.sh backup
```

## 🔧 Управление конфигурацией

### Установка и обновление
```bash
# Первоначальная установка
./install.sh

# Установка без опциональных инструментов
./install.sh --no-optional

# Обновление конфигурации
./scripts/update.sh

# Проверка целостности
./scripts/verify_installation.sh
```

### Резервное копирование и восстановление
```bash
# Создание резервной копии перед изменениями
cp ~/.zshrc ~/.zshrc.backup

# Восстановление из автоматической резервной копии
# (ищите в ~/.dotfiles_backup_YYYYMMDD_HHMMSS/)

# Безопасное удаление с восстановлением
./scripts/uninstall.sh
```

## 💡 Полезные горячие клавиши

```bash
Ctrl+R    # Интерактивный поиск в истории (fzf)
↑ / ↓     # Навигация по истории с учетом введенного текста
Ctrl+L    # Очистить экран
Ctrl+A    # Перейти в начало строки
Ctrl+E    # Перейти в конец строки
Ctrl+U    # Удалить от курсора до начала строки
Ctrl+K    # Удалить от курсора до конца строки
```

## 🛠️ Настройка под себя

### Добавление собственных алиасов
```bash
# Отредактируйте файл
vim ~/.dotfiles/.zsh_aliases

# Добавьте свои алиасы, например:
alias myproject='cd ~/Documents/MyProject'
alias ll='ls -la'
alias grep='grep --color=auto'

# Перезагрузите конфигурацию
source ~/.zshrc
```

### Настройка игнорирования команд в истории
```bash
# Отредактируйте ~/.dotfiles/.zsh_history_config
vim ~/.dotfiles/.zsh_history_config

# Найдите строку HISTORY_IGNORE и добавьте свои команды:
HISTORY_IGNORE="(ls|cd|pwd|exit|clear|history|htop|top)"
```

### Изменение размера истории
```bash
# Отредактируйте ~/.dotfiles/.zshrc
vim ~/.dotfiles/.zshrc

# Найдите и измените:
HISTSIZE=200000    # Увеличить до 200,000
SAVEHIST=200000
```

## 🚀 Продвинутые примеры

### Поиск и анализ истории
```bash
# Найти все команды с git за последнюю неделю
history_by_date $(date -d '7 days ago' +%Y-%m-%d)

# Экспорт истории в файл для анализа
export_history ~/my_history_export.txt

# Поиск команд по шаблону
hist_grep "docker.*run"

# Статистика использования команд
history_stats | head -20
```

### Работа с резервными копиями
```bash
# Создать именованную резервную копию истории
backup_history

# Импорт истории из другого файла
import_history ~/old_history.txt

# Очистка старых резервных копий (автоматически каждые 10 запусков)
# Ручная очистка:
find ~/.dotfiles/history_backups/ -name "*.bak" -mtime +30 -delete
```

### Интеграция с другими инструментами
```bash
# Использование с tmux
# История синхронизируется между всеми панелями

# Использование с fzf для других задач
# Поиск файлов: Ctrl+T
# Поиск директорий: Alt+C
# Поиск в истории: Ctrl+R

# Интеграция с git
git log --oneline | fzf | cut -d' ' -f1 | xargs git show
```

## 🔧 Устранение неполадок

### История не работает
```bash
# Проверить настройки
echo $HISTFILE
echo $HISTSIZE
echo $SAVEHIST

# Проверить права доступа
ls -la ~/.dotfiles/.zsh_history

# Пересоздать файл истории
touch ~/.dotfiles/.zsh_history
chmod 600 ~/.dotfiles/.zsh_history
```

### Функции недоступны
```bash
# Проверить загрузку конфигурации
source ~/.dotfiles/.zsh_history_config

# Проверить наличие файлов
ls -la ~/.dotfiles/.zsh_*

# Проверить синтаксис
zsh -n ~/.zshrc
```

### Медленная загрузка shell
```bash
# Профилирование загрузки
time zsh -i -c exit

# Отключить медленные плагины временно
# Закомментируйте строки в ~/.zshrc

# Оптимизация истории
~/.dotfiles/scripts/history_maintenance.sh dedupe
```

## 📈 Мониторинг и оптимизация

### Регулярное обслуживание
```bash
# Еженедельно: дедупликация истории
~/.dotfiles/scripts/history_maintenance.sh dedupe

# Ежемесячно: анализ использования
~/.dotfiles/scripts/history_maintenance.sh analyze

# По необходимости: очистка старых резервных копий
find ~/.dotfiles/history_backups/ -name "*.bak" -mtime +90 -delete
```

### Проверка производительности
```bash
# Размер файла истории
ls -lh ~/.dotfiles/.zsh_history

# Количество команд
wc -l ~/.dotfiles/.zsh_history

# Топ команд за сегодня
fc -l 1 | grep "$(date +%Y-%m-%d)" | awk '{print $4}' | sort | uniq -c | sort -nr | head -10
```

Эти примеры помогут вам максимально эффективно использовать улучшенную конфигурацию dotfiles!
