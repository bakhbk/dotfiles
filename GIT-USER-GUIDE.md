# Git Multi-Identity Setup

Правило: в `~/.gitconfig` никогда не задавать `[user]` — идентичности живут
в отдельных локальных файлах, которые не попадают в публичный репозиторий.

## Схема

| Каталог | Файл идентичности |
|---|---|
| `~/projects/**` | `~/.gitconfig-personal` |
| `~/work/**` | `~/.gitconfig-work` |
| остальное | (пусто) |

`includeIf` в `.gitconfig` выбирает файл по пути репозитория. Реальные имена
и email нигде не хранятся в этом репозитории.

## Установка на новой машине

```bash
cp ~/dotfiles/.gitconfig ~/.gitconfig
cp ~/dotfiles/git/gitconfig-personal.example ~/.gitconfig-personal   # заполнить
cp ~/dotfiles/git/gitconfig-work.example ~/.gitconfig-work           # заполнить
```

## Проверка

```bash
cd ~/projects && git config user.name && git config user.email
```
