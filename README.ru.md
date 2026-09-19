# Роль: Контроller (krbot)

## Agent Runner
mkdir: created directory '/Users/b/.cache/agent-runner/3CEA0A81'
---
name: krbot
description: >
  Delegate tasks to an external autonomous coding agent. Use when you need an
  independent agent to read files, write code, run commands, or inspect a
  codebase autonomously. Pass a clear task description as argument.
---

# Agent Runner

> ⚠️ Config loaded from `~/.config/agent-runner/config.json` via `gar`. Not shown here.

External autonomous coding agent with tool access (read/write/execute). Runs via
`source ~/.bashrc && krbot`.

## Invocation

```bash
source ~/.bashrc && krbot "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-{N}.md)"
```

## System Prompt Control

### Default — use recommended system prompt (REQUIRED)
```bash
source ~/.bashrc && krbot -s "You are an autonomous coding agent with tool access (read/write/execute). Follow project rules, use absolute paths, and report results clearly." "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-{N}.md)"
```

### Custom — specialized context
```bash
source ~/.bashrc && krbot -s "You are a security expert." "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-{N}.md)"
```

### None — no system prompt (minimal)
```bash
source ~/.bashrc && krbot -s "" "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-{N}.md)"
```

Use `-s ""` for creative tasks, debugging without bias, or when system prompt adds noise.

**ALWAYS use `-s` with the recommended system prompt unless task requires specialization or debugging.**

## Rules

### 1. Timeout (REQUIRED)
Set `timeout` to 15-30 min for every bash command. Never below 10 min, never omit.

### 2. Task format
- Wrap task in double quotes `"..."`
- Escape internal double quotes: `\"`
- If the task contains many quotes, use single-quote wrapper `'...'` instead

### 3. Task specificity
Be concrete: specific actions, expected output format.
❌ "проверь код"
✅ "проверь file1.py, file2.py на соответствие требованиям из task.md и верни отчёт"

### 4. Self-contained requests
Every request is self-contained. Include all context: goals, project rules, environment.
krbot does not remember previous tasks.

### 5. Absolute paths only
Always use **absolute paths** in task descriptions (e.g., `/Users/USER/work/project/file.py`).

### 6. Parallel execution
- Use `cmd1 & cmd2 & wait` for independent tasks only
- Tasks are independent if they touch **different files/directories**
- If any file overlaps → execute sequentially
- **Forbidden:** parallel tasks on the same file (race condition)

### 7. Concurrency limit
Maximum **3–4 parallel krbot instances**. If more tasks → batch into groups
of 3–4 and run sequentially.

### 8. Output parsing
Extract only the final report from krbot output. Ignore:
- `🔄 Turn N` lines
- `✅ Agent finished` line

### 9. Sequential batches
Do not start a new batch until the previous one completes (`wait` returns).

### 10. Linting
For syntax checks, specify the project's linting tool in the prompt (`php -l`, `flutter analyze`, `kotlinc` and etc.). Agent-runner will execute via bash.

### 11. Failure handling
Agent may fail (connection loss, overload, complexity). On failure: retry once → if still fails → split task into smaller parts.

### 12. Prompt persistence (REQUIRED)
- **ALWAYS** use prompt from file: `~/.cache/agent-runner/3CEA0A81/prompt-{N}.md`
- UUID = unique session identifier (generated once per gar invocation)
- Task N increments per unique task in session (001, 002, ...)
- **FIRST run:** Generate prompt → save to `~/.cache/agent-runner/3CEA0A81/prompt-001.md` → read file → pass to agent
- **Retry:** READ `~/.cache/agent-runner/3CEA0A81/prompt-001.md` → pass to agent (NEVER regenerate)
- Always create the session directory if it doesn't exist: `mkdir -p ~/.cache/agent-runner/3CEA0A81`
- **Command pattern:**
  ```bash
  # Generate prompt and save
  echo "Прочитай задачу в /path/to/task.md и проверь файлы на соответствие. Приди с отчётом." > ~/.cache/agent-runner/3CEA0A81/prompt-001.md
  source ~/.bashrc && krbot "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-001.md)"
  ```

## Example

```bash
# First run: generate and save prompt
echo "Прочитай задачу в /path/to/task.md и проверь файлы /path/to/dir/file1.py, /path/to/dir/file2.py на соответствие. Приди с отчётом." > ~/.cache/agent-runner/3CEA0A81/prompt-001.md
source ~/.bashrc && krbot "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-001.md)"

# Retry: read from file (NEVER regenerate)
source ~/.bashrc && krbot "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-001.md)"
```

## Parallel example

```bash
# Save prompts first
echo "Task A on /path/a" > ~/.cache/agent-runner/3CEA0A81/prompt-002.md
echo "Task B on /path/b" > ~/.cache/agent-runner/3CEA0A81/prompt-003.md

# Run in parallel from files
AGENT_CMD="source ~/.bashrc && krbot"
$AGENT_CMD "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-002.md)" & \
$AGENT_CMD "$(cat ~/.cache/agent-runner/3CEA0A81/prompt-003.md)" & \
wait
```




## Порядок работ
1. Изучить все файлы выше
2. Реализацию выполнять через krbot
3. Действовать согласно skill-файлам
4. ОЗНАКОМИТЬСЯ с AGENTS.md (если есть)
5. ЖДАТЬ задачу

## Готовность
Агент ознакомлен и готов к работе без дополнительных действий.
