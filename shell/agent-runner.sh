# =============================================================
# Agent Runner — gar, load-skill и хелперы
# =============================================================

_config_file="$HOME/.config/agent-runner/config.json"
_skill_template="$HOME/.agents/skills/agent-runner/SKILL.md"
_prompt_template="$HOME/.agents/prompts/load-agent-skill.template.md"

# ---------------------------------------------------------------
# __pick_agent — fzf выбор агента из config.json
# Возвращает имя агента (stdout) или 1 при сбое
# ---------------------------------------------------------------
__pick_agent() {
    if [ ! -f "$_config_file" ]; then
        echo "❌ Config not found: $_config_file" >&2
        return 1
    fi

    # Check required tools before fzf
    if ! command -v jq >/dev/null 2>&1; then
        echo "❌ jq is required but not found" >&2
        return 1
    fi

    if ! command -v fzf >/dev/null 2>&1; then
        echo "❌ fzf is required but not found" >&2
        return 1
    fi

    local agent
    agent=$(jq -r '.agents | keys[]' "$_config_file" 2>/dev/null | \
            fzf --preview-window=wrap --preview "jq '.agents[\"{}\"]' $_config_file" 2>/dev/null)

    # Check fzf result (was empty or cancelled)
    if [ -z "$agent" ]; then
        local agent_count
        agent_count=$(jq '.agents | keys | length' "$_config_file" 2>/dev/null)
        if [ "${agent_count:-0}" -eq 0 ]; then
            echo "❌ No agents found in config: $_config_file" >&2
        else
            echo "❌ No agent selected (cancelled or fzf failed)" >&2
        fi
        return 1
    fi
    echo "$agent"
}

# ---------------------------------------------------------------
# __render_skill_md — рендерит SKILL.md шаблона из конфига
# Возвращает готовый текст (stdout)
# Генерирует UUID, создаёт session-директорию (для gar)
# ---------------------------------------------------------------
__render_skill_md() {
    local agent="$1"
    local config_file="$_config_file"
    local force_uuid="${2:-}"

    if [ ! -f "$config_file" ]; then
        echo "❌ Config not found: $config_file" >&2
        return 1
    fi

    local invocation system_prompt_flag prompt_prefix uuid
    invocation=$(jq -r ".agents[\"$agent\"].invocation" "$config_file")
    if [ "$invocation" = "null" ]; then
        echo "❌ Agent not found in config: $agent" >&2
        return 1
    fi
    system_prompt_flag=$(jq -r ".agents[\"$agent\"].system_prompt_flag // empty" "$config_file")
    prompt_prefix=$(jq -r ".agents[\"$agent\"].prompt_prefix" "$config_file")

    # UUID fallback: uuidgen → date → error
    if [ -z "$force_uuid" ]; then
        if command -v uuidgen >/dev/null 2>&1; then
            uuid=$(uuidgen | cut -c1-8)
        elif command -v date >/dev/null 2>&1; then
            # Fallback: use epoch seconds as pseudo-unique ID
            uuid=$(date +%s | cut -c1-8)
        else
            echo "❌ Cannot generate session ID (no uuidgen or date)" >&2
            return 1
        fi
    else
        uuid="$force_uuid"
    fi

    # Validate uuid is not empty (protects against data corruption)
    if [ -z "$uuid" ]; then
        echo "❌ Failed to generate a valid UUID" >&2
        return 1
    fi

    # Auto-create session directory
    mkdir -p "$HOME/.cache/agent-runner/$uuid" 2>/dev/null

    # Clean old prompt directories (>7 days)
    find "$HOME/.cache/agent-runner" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null

    # Validate template file exists before calling python3
    if [ ! -f "$_skill_template" ]; then
        echo "❌ Skill template not found: $_skill_template" >&2
        return 1
    fi

    if [ -z "$system_prompt_flag" ]; then
        python3 -c "
import re, sys
template = open(sys.argv[1]).read()
template = re.sub(r'## System Prompt Control\n.*?(?=## Rules)', '', template, flags=re.DOTALL)
template = template.replace('{{AGENT_NAME}}', sys.argv[2])
template = template.replace('{{INVOCATION}}', sys.argv[3])
template = template.replace('{{PROMPT_PREFIX}}', sys.argv[4])
template = template.replace('{{SESSION_UUID}}', sys.argv[5])
print(template, end='')
" "$_skill_template" "$agent" "$invocation" "$prompt_prefix" "$uuid"
    else
        python3 -c "
import sys
template = open(sys.argv[1]).read()
template = template.replace('{{AGENT_NAME}}', sys.argv[2])
template = template.replace('{{INVOCATION}}', sys.argv[3])
template = template.replace('{{SYSTEM_PROMPT_FLAG}}', sys.argv[4])
template = template.replace('{{PROMPT_PREFIX}}', sys.argv[5])
template = template.replace('{{SESSION_UUID}}', sys.argv[6])
print(template, end='')
" "$_skill_template" "$agent" "$invocation" "$system_prompt_flag" "$prompt_prefix" "$uuid"
    fi
}

# ---------------------------------------------------------------
# __copy_to_clipboard — копирует содержимое файла в буфер
# Аргумент: путь к файлу
# ---------------------------------------------------------------
__copy_to_clipboard() {
    local src="$1"
    if command -v pbcopy >/dev/null 2>&1; then
        cat "$src" | pbcopy
    elif command -v wl-copy >/dev/null 2>&1; then
        cat "$src" | wl-copy
    elif command -v xclip >/dev/null 2>&1; then
        cat "$src" | xclip -selection clipboard
    else
        echo "⚠️  No clipboard tool found (pbcopy/wl-copy/xclip)" >&2
        return 1
    fi
}

# ---------------------------------------------------------------
# gar — Generate Agent Runner
# Выбирает агента, рендерит SKILL.md, копирует в буфер
# ---------------------------------------------------------------
gar() {
    local edit_mode=false
    local run_mode=false
    local dry_run_mode=false
    local help_mode=false
    local task=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -e|--edit)   edit_mode=true; shift ;;
            -d|--dry-run) dry_run_mode=true; shift ;;
            -r|--run)    run_mode=true; shift; task="$*"; break ;;
            -h|--help)   help_mode=true; shift ;;
            *)           shift ;;
        esac
    done

    # Show help if requested
    if $help_mode; then
        echo "Usage: gar [-e|-d|-r \"task\"]"
        echo ""
        echo "Options:"
        echo "  -e, --edit      Open rendered SKILL.md in \$EDITOR, then copy to clipboard"
        echo "  -d, --dry-run   Show rendered SKILL.md in terminal (no clipboard)"
        echo "  -r, --run \"task\" Render and pass directly to pi with task"
        echo "  -h, --help      Show this help message"
        echo ""
        echo 'Config: ~/.config/agent-runner/config.json'
        echo '  {'
        echo '    "agents": {'
        echo '      "<name>": {'
        echo '        "invocation": "...",'
        echo '        # optional:'
        echo '        "system_prompt_flag": "...",'
        echo '        "prompt_prefix": "..."'
        echo '      }'
        echo '    }'
        echo '  }'
        echo ''
        echo "Default: render and copy to clipboard"
        return 0
    fi

    # Select agent via fzf with preview
    local agent
    agent=$(__pick_agent) || return

    [ -z "$agent" ] && return
    echo "✓ Selected agent: $agent" >&2

    # Render SKILL.md
    local rendered
    rendered=$(__render_skill_md "$agent") || return

    # Записываем в темп-файл (pbcopy падает на больших текстах из echo)
    local tmp_file
    tmp_file=$(mktemp /tmp/skill-XXXXXX.md)
    printf '%s\n' "$rendered" > "$tmp_file"

    if $run_mode; then
        if ! command -v pi >/dev/null 2>&1; then
            echo "❌ 'pi' command not found — run mode requires pi" >&2
            return 1
        fi
        echo "🚀 Running agent $agent with task: $task" >&2
        pi --skill "$tmp_file" -p "$task"
        rm -f "$tmp_file"

    elif $edit_mode; then
        local editor="${EDITOR:-nvim}"
        $editor "$tmp_file"
        if __copy_to_clipboard "$tmp_file"; then
            echo "✓ Rendered SKILL.md for $agent copied to clipboard" >&2
        else
            echo "⚠️  Copied to editor, but clipboard tool unavailable" >&2
        fi
        rm -f "$tmp_file"

    elif $dry_run_mode; then
        cat "$tmp_file"

    else
        # default: copy to clipboard
        if __copy_to_clipboard "$tmp_file"; then
            echo "✓ Rendered SKILL.md for $agent copied to clipboard" >&2
        else
            echo "⚠️  No clipboard tool available (pbcopy/wl-copy/xclip missing)" >&2
            # Fallback: print to stdout as last resort
            cat "$tmp_file"
        fi
        rm -f "$tmp_file"
    fi

    rm -f "$tmp_file"
}

# ---------------------------------------------------------------
# load-skill — assemble mega-prompt
# Выбирает агента, рендерит его SKILL.md (на лету из конфига),
# вставляет в шаблон, копирует в буфер.
# Аргументы — optional skill-названия (для реальных директорий)
# Агенты сами НЕ существуют как директории — генерируются gar-ом.
# ---------------------------------------------------------------
load-skill() {
    local edit_mode=false
    local dry_run_mode=false
    local help_mode=false
    local skills=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -e|--edit)   edit_mode=true; shift ;;
            -d|--dry-run) dry_run_mode=true; shift ;;
            -h|--help)
                echo "Usage: load-skill [-e|-d] [SKILL_NAME...]"
                echo ""
                echo "Assembles a mega-prompt: Agent SKILL.md (generated on the fly) + optional skill dirs."
                echo ""
                echo "Options:"
                echo "  -e, --edit      Open mega-prompt in \$EDITOR"
                echo "  -d, --dry-run   Show in terminal (no clipboard)"
                echo "  -h, --help      Show this help"
                echo ""
                echo "Note: agents are generated from config.json, not filesystem dirs."
                echo "Optional SKILL_NAME args refer to real skill directories under"
                echo "  ~/.agents/skills/<agent>/"
                return 0 ;;
            *) skills+=("$1"); shift ;;
        esac
    done

    # Pick agent via fzf
    local agent
    agent=$(__pick_agent) || return
    [ -z "$agent" ] && return
    echo "✓ Selected agent: $agent" >&2

    # Generate UUID for session dir (shared between gar and load-skill)
    local uuid
    if command -v uuidgen >/dev/null 2>&1; then
        uuid=$(uuidgen | cut -c1-8)
    elif command -v date >/dev/null 2>&1; then
        uuid=$(date +%s | cut -c1-8)
    else
        echo "❌ Cannot generate session ID (no uuidgen or date)" >&2
        return 1
    fi
    [ -z "$uuid" ] && { echo "❌ Failed to generate a valid UUID" >&2; return 1; }

    # Validate required tools before proceeding
    if ! command -v python3 >/dev/null 2>&1; then
        echo "❌ python3 is required but not found" >&2
        return 1
    fi

    # Render agent SKILL.md (generated on the fly — pass UUID)
    local rendered_skill_md
    rendered_skill_md=$(__render_skill_md "$agent" "$uuid") || return

    # Build skills section from optional named skill directories
    local tmpdir
    tmpdir=$(mktemp -d)
    local skills_section=""

    if [ ${#skills[@]} -gt 0 ]; then
        for skill in "${skills[@]}"; do
            local full_dir="$HOME/.agents/skills/$agent/$skill"
            if [ -d "$full_dir" ]; then
                local file_content=""
                while IFS= read -r file; do
                    [ -z "$file" ] && continue
                    local rel_path="${file#$full_dir/}"
                    file_content+=$'\n'"### File: $rel_path"$'\n'
                    file_content+="$(cat "$file")"$'\n'
                done < <(find "$full_dir" -type f | sort)
                skills_section+=$'\n'"## $skill"$file_content
            else
                echo "⚠️  Not found: $full_dir" >&2
            fi
        done
    fi

    # Validate template files before processing
    if [ ! -f "$_prompt_template" ]; then
        echo "❌ Prompt template not found: $_prompt_template" >&2
        return 1
    fi

    # Render template with python (safe — reads from files)
    echo "$rendered_skill_md" > "$tmpdir/skill.md"
    printf '%s' "$skills_section" > "$tmpdir/skills.md"

    local mega_prompt
    mega_prompt=$(python3 -c "
import sys, os
template = open(sys.argv[1]).read()
agent_skill = open(sys.argv[2]).read()
skills = open(sys.argv[3]).read()
template = template.replace('{{AGENT_NAME}}', sys.argv[4])
template = template.replace('{{AGENT_RUNNER_SKILL}}', agent_skill)
template = template.replace('{{SKILLS_SECTION}}', skills)
print(template, end='')
" "$_prompt_template" "$tmpdir/skill.md" "$tmpdir/skills.md" "$agent")

    # Write to temp file (reliable for large text)
    local tmp_file
    if ! command -v mktemp >/dev/null 2>&1; then
        echo "❌ mktemp is required but not found" >&2
        return 1
    fi
    tmp_file=$(mktemp /tmp/mega-prompt-XXXXXX.md)
    printf '%s\n' "$mega_prompt" > "$tmp_file"

    # Save to session directory (so gar can read it back)
    local session_dir="$HOME/.cache/agent-runner/$uuid"
    mkdir -p "$session_dir" 2>/dev/null
    cp "$tmp_file" "$session_dir/mega-prompt.md"
    echo "✓ Saved to $session_dir/mega-prompt.md" >&2

    if $edit_mode; then
        local editor="${EDITOR:-nvim}"
        $editor "$tmp_file"
        rm -f "$tmp_file"

    elif $dry_run_mode; then
        cat "$tmp_file"
        rm -f "$tmp_file"

    else
        __copy_to_clipboard "$tmp_file"
        rm -f "$tmp_file"
        echo "✓ Mega-prompt for $agent copied to clipboard" >&2
    fi

    rm -rf "$tmpdir"
}