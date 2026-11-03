# pi() — workspace-aware session directory (base-<name>/sessions), global fallback.
# Precedence: --session-dir > detected base-* ancestor > PI_CODING_AGENT_SESSION_DIR > global.

PI_GLOBAL_SESSION_DIR="${PI_GLOBAL_SESSION_DIR:-$HOME/.pi/agent/sessions}"

_pi_base_dir() {
  local d="$PWD"
  while [[ $d != "/" ]]; do
    if [[ ${d##*/} == base-* ]]; then print -r -- "$d"; return 0; fi
    d="${d:h}"
  done
  return 1
}

_pi_session_path() {
  local id="$1" dir found
  [[ -f $1 ]] && { print -r -- "$1"; return 0 }
  for dir in "$2" "$PI_GLOBAL_SESSION_DIR"; do
    [[ -z $dir || ! -d $dir ]] && continue
    found=$(find "$dir" -name "*_${id}.jsonl" -print -quit 2>/dev/null)
    [[ -n $found ]] && { print -r -- "$found"; return 0 }
  done
  return 1
}

pi() {
  local base sessdir spath args=()
  base=$(_pi_base_dir)
  sessdir="${base:+$base/sessions}"
  [[ -z $sessdir ]] && sessdir="${PI_CODING_AGENT_SESSION_DIR:-$PI_GLOBAL_SESSION_DIR}"
  while (($#)); do
    case $1 in
      --session-dir)
        (($# >= 2)) && { sessdir="$2"; args+=("$1" "$2"); shift 2 } || { args+=("$1"); shift } ;;
      --session| --fork)
        if (($# >= 2)); then
          spath=$(_pi_session_path "$2" "$sessdir")
          args+=("$1" "${spath:-$2}"); shift 2
        else args+=("$1"); shift; fi ;;
      *) args+=("$1"); shift ;;
    esac
  done
  [[ -n $base ]] && export PI_CODING_AGENT_SESSION_DIR="$sessdir"
  command pi "${args[@]}"
}
