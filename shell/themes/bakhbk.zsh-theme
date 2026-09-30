# Дата, временем и git-статусом на строке над промптом: 01-15 20:33 *2!3?1 +2 ↓1 ⇡ ✹
# Сбрасываем RPROMPT, если он остался от другой версии темы
unset RPROMPT

# Git-статус (по мотивам bureau.zsh-theme из oh-my-zsh):
#   *n  — n staged: файлы добавлены в index (git add) и готовы к коммиту
#   !n  — n изменённых: правки в рабочих файлах, не добавлены в index
#         (включает deleted и конфликты)
#   ?n  — n untracked: новые файлы, git их не отслеживает (не git add-нуто)
#   +n  — ahead: ваши коммиты ещё не пушнуты в remote
#   ↓n  — behind: в remote есть коммиты, которых нет у вас (нужен pull)
#   +n ↓n вместе — diverged: вы и remote разошлись, нужен pull --rebase/merge
#   ⇡   — нет upstream: ветка ещё никогда не пушалась (нет push -u)
#   ✹n  — n stashed: записи в git stash
#   ничего не выводится — репо чистое и синхронное с remote
_bakhbk_git_status() {
  local -a lines=("${(@f)$(command git status --porcelain -b 2>/dev/null)}")
  (( ${#lines[@]} == 0 )) && return

  local staged=0 modified=0 untracked=0 xy
  for xy in $lines; do
    [[ "$xy" == "## "* ]] && continue
    if [[ "${xy:0:2}" == '??' ]]; then
      (( untracked++ ))
    else
      [[ "${xy:0:1}" == [MADRC] ]] && (( staged++ ))
      [[ "${xy:1:1}" == [MTD] || "${xy:0:2}" == 'UU' ]] && (( modified++ ))
    fi
  done

  local out='' sep=' '
  (( staged    )) && out+="${sep}%{%F{green}%}*${staged}%{%f%}"
  (( modified  )) && out+="${sep}%{%F{yellow}%}!${modified}%{%f%}"
  (( untracked )) && out+="${sep}%{%F{magenta}%}?${untracked}%{%f%}"

  # ahead/behind из первой строки: ## main...origin/main [ahead 2, behind 1]
  local re='[[:space:]]\(([^)]*)\)$' flags
  if [[ "${lines[1]}" == "## "* && "${lines[1]}" =~ $re ]]; then
    flags="${match[1]}"
    [[ "$flags" =~ ahead\ ([0-9]+) ]]  && out+="${sep}%{%F{cyan}%}+${match[1]}%{%f%}"
    [[ "$flags" =~ behind\ ([0-9]+) ]] && out+="${sep}%{%F{cyan}%}↓${match[1]}%{%f%}"
  fi

  # Ветка без upstream (не пушена)
  if [[ "${lines[1]}" == "## "* && "${lines[1]}" != *"..."* && "${lines[1]}" != "## HEAD"* ]]; then
    out+="${sep}%{%F{blue}%}⇡%{%f%}"
  fi

  # Stash
  local stashes="$(command git stash list 2>/dev/null)"
  if [[ -n "$stashes" ]]; then
    local -a stash_list=(${(@f)stashes})
    out+="${sep}%{%F{magenta}%}✹${#stash_list[@]}%{%f%}"
  fi

  [[ -n "$out" ]] && print -n "$out"
}

PROMPT=$'%F{240}◷  %D{%m-%d %H:%M}$(_bakhbk_git_status)\n%f'
PROMPT+='%(?:%{$fg_bold[green]%}%1{➜%} :%{$fg_bold[red]%}%1{➜%} ) %{$fg[cyan]%}%c%{$reset_color%}'
PROMPT+=' $(git_prompt_info)'

ZSH_THEME_GIT_PROMPT_PREFIX="%{$fg_bold[blue]%}git:(%{$fg[red]%}"
ZSH_THEME_GIT_PROMPT_SUFFIX="%{$reset_color%} "
ZSH_THEME_GIT_PROMPT_DIRTY="%{$fg[blue]%}) %{$fg[yellow]%}%1{✗%}"
ZSH_THEME_GIT_PROMPT_CLEAN="%{$fg[blue]%})"
