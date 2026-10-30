#!/usr/bin/env zsh
# Check that the OS adapter layer defines every primitive on the current platform.
# Run on macOS and Linux after ./install.sh.
set -u

DIR="${1:-$HOME/.dotfiles}"
export DOTFILES_DIR="$DIR"
source "$DIR/zsh_compat"

typeset -a fns=(
  _clip_copy _clip_paste _local_ip _iface _gateway _open_file
  _lock_file _unlock_file _cache_dir _adb_path _net_ifaces _list_ports _pkg_install _dns_servers
)

fail=0
for n in $fns; do
  if (( ! $+functions[$n] )); then
    echo "❌ missing: $n"
    fail=1
  fi
done

(( $+_OS )) || { echo "❌ _OS not set"; fail=1; }
[[ $_OS = unknown ]] && { echo "❌ _OS=unknown (OSTYPE=$OSTYPE)"; fail=1; }

print "OS: $_OS"
print "local ip:   $(_local_ip)"
print "gateway:    $(_gateway)"
print "cache root: $CACHE_ROOT"
print "clipboard:  $(echo test | _clip_copy >/dev/null 2>&1 && echo ok || echo 'no clipboard tool')"

exit $fail
