#!/usr/bin/env bash
# install-agent.sh — создаёт ~/.local/bin/agent обёртку на macOS / Linux
#
# Примеры:
#   bash install-agent.sh                         # создать
#   bash install-agent.sh --aigent /path/aigent.py # свой путь
#   bash install-agent.sh --remove                # удалить
#   bash install-agent.sh --help                  # справка
#
# После создания:  agent "задача"  — из любой директории.
#
# Принципы при редактировании файла:
#   KISS     — одна задача на строку, минимум абстракций, без «умных» трюков
#   YAGNI    — только то, что нужно сейчас; без форса «на всякий случай»
#   DRY      — один путь, один источник истины (переменные, не строки пути)
#   TESTABLE — каждый блок независим, легко проверить по отдельности
#   COMPACT  — 30-50 строк; без комментариев-баннеров и повторов

set -euo pipefail

# --- Аргументы ---
AIGENT_PATH=""
REMOVE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove|-r)         REMOVE=1;     shift ;;
    --aigent|--path|-p)  AIGENT_PATH="$2"; shift 2 ;;
    --help|-h)           echo "Создаёт ~/.local/bin/agent — обёртку для aigent.py через uv.
  Примеры:
    $0                          # создать (по умолчанию ~/dotfiles/scripts/aigent.py)
    $0 --aigent /path/to/aigent.py  # указать путь явно
    $0 --remove                 # удалить обёртку
  После создания:  agent \"задача\"  — из любой директории."; exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

TARGET="$HOME/.local/bin/agent"

# --- Удаление ---
if [[ "$REMOVE" -eq 1 ]]; then
  rm -f "$TARGET" && echo "Removed $TARGET" && exit 0
fi

# --- Поиск aigent.py ---
if [[ -z "$AIGENT_PATH" ]]; then
  AIGENT_PATH="$(eval echo ~/dotfiles/scripts/aigent.py 2>/dev/null)"
fi
[[ -f "$AIGENT_PATH" ]] || { echo "aigent.py не найден: $AIGENT_PATH" >&2; exit 1; }

# --- Проверка uv ---
command -v uv &>/dev/null || { echo "uv не найден в PATH." >&2; exit 1; }

# --- Создание обёртки ---
mkdir -p "$HOME/.local/bin"

cat > "$TARGET" <<EOF
#!/usr/bin/env bash
exec uv run $(realpath "$AIGENT_PATH") "\$@"
EOF
chmod +x "$TARGET"

echo "✅ $TARGET создан"
