---
name: git-multi-user
description: Set up git multi-user routing by directory. Use when configuring git user, setting up a new Mac, or switching between personal and work git identities. Never set a global [user] in ~/.gitconfig — always route through includeIf.
---

# Git Multi-User Setup

## Главное правило

**Никогда не задавать `[user]` в основном `~/.gitconfig`!**

Git читает конфиги сверху вниз, и **последний заданный ключ побеждает**. Если глобальный `[user]` существует в `~/.gitconfig`, он переопределит то, что включено через `includeIf`.

## Правильный подход

Определять всех пользователей через `includeIf` по директориям. Каждый путь — отдельный конфиг-файл.

## Структура

```
~/.gitconfig           → маршрутизация (без [user])
~/.gitconfig-personal  → личный пользователь
~/.gitconfig-work      → рабочий пользователь
~/.gitconfig-XXX       → пользователь для зоны XXX
```

## Быстрый старт (настройка за 1 минуту)

```bash
# 1. Создать файлы пользователей
cat > ~/.gitconfig-personal << 'EOF'
[user]
    name = Your Name
    email = you@example.com
EOF

cat > ~/.gitconfig-work << 'EOF'
[user]
    name = Work Name
    email = work@company.com
EOF

# 2. Убедиться, что ~/.gitconfig содержит только includeIf
cat > ~/.gitconfig << 'EOF'
[core]
    editor = vim
[includeIf "gitdir:~/own_projects/**"]
    path = ~/.gitconfig-personal
[includeIf "gitdir:~/work/XXX/**"]
    path = ~/.gitconfig-work
EOF

# 3. Проверить
cd ~/own_projects/project && git config user.name   # Your Name
cd ~/work/XXX/project && git config user.name       # Work Name
```

## Проверка текущей настройки

```bash
# Показать какой юзер используется в текущей директории
git config user.name
git config user.email

# Показать все подключённые конфиги (включая includeIf)
git config --list --show-origin | grep -E '(user|include)'

# Показывает, какие includeIf сработали
git config --list --show-origin
```

## Добавить новую зону

```bash
# 1. Создать файл пользователя
cat > ~/.gitconfig-название << 'EOF'
[user]
    name = Имя
    email = email@домен.com
EOF

# 2. Добавить includeIf в ~/.gitconfig
echo '[includeIf "gitdir:/путь/**"]' >> ~/.gitconfig
echo '    path = ~/.gitconfig-название' >> ~/.gitconfig

# 3. Проверить
cd /путь/репо && git config user.name
```

## Удаление зоны

```bash
# 1. Удалить строку includeIf из ~/.gitconfig
# 2. Удалить файл ~/.gitconfig-название
```

## Примеры конфигураций

### Для проектов в ~/projects
```ini
[includeIf "gitdir:~/projects/**"]
    path = ~/.gitconfig-personal
```

### Для рабочих проектов в ~/work/компания
```ini
[includeIf "gitdir:~/work/компания/**"]
    path = ~/.gitconfig-work
```

### Для всех проектов в /home/user/code
```ini
[includeIf "gitdir:/home/user/code/**"]
    path = ~/.gitconfig-code
```

## Чек-лист при настройке нового Mac

1. [ ] Создать `~/.gitconfig` (только `core` + `includeIf`, без `[user]`)
2. [ ] Создать `~/.gitconfig-personal` (личный пользователь)
3. [ ] Создать `~/.gitconfig-work` (рабочий пользователь)
4. [ ] Проверить: `cd ~/own_projects && git config user.name`
5. [ ] Проверить: `cd ~/work/KR && git config user.name`
6. [ ] Добавить другие зоны по необходимости

## Возможные команды для скилла

- `/skill:git-multi-user setup` — быстрая настройка с вопросами
- `/skill:git-multi-user check` — проверить текущую конфигурацию
- `/skill:git-multi-user add <путь> <имя> <email>` — добавить новую зону
- `/skill:git-multi-user remove <название>` — удалить зону
