# Git Multi-User Setup

## Правило: Никогда не задавать `[user]` в основном `~/.gitconfig`!

Всё определяется через `includeIf` по директориям. Глобальный `[user]` переопределяет включённые файлы.

## Схема

| Директория | User | Email |
|---|---|---|
| `~/own_projects/**` | `bakhbk` | `bakhbk@gmail.com` |
| `/Users/b/work/KR/**` | `Nazarov Bakhodur` | `bobonazarov@kr.digital` |
| Всё остальное | (пусто) | (пусто) |

## Файлы

- `~/.gitconfig` — маршрутизация (без `[user]`)
- `~/.gitconfig-default` — основной пользователь (own_projects)
- `~/.gitconfig-work` — рабочий пользователь (KR)

## Восстановление на новом Mac

```bash
# 1. Копируем конфиги
cp ~/dotfiles/.gitconfig ~/.gitconfig
cp ~/dotfiles/.gitconfig-default ~/.gitconfig-default
cp ~/dotfiles/.gitconfig-work ~/.gitconfig-work

# 2. Проверяем
cd ~/own_projects && git config user.name   # bakhbk
cd ~/work/KR  && git config user.name       # Nazarov Bakhodur
```

## Проверка в текущей директории

```bash
git config user.name
git config user.email
```

## Добавить новую зону

```bash
# 1. Создать конфиг
cat > ~/.gitconfig-newzone << 'EOF'
[user]
    name = New User
    email = new@example.com
EOF

# 2. Добавить в ~.gitconfig
echo '[includeIf "gitdir:/путь/**"]' >> ~/.gitconfig
echo '    path = ~/.gitconfig-newzone' >> ~/.gitconfig
```
