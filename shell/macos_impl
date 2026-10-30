# macOS (BSD) implementation of the primitives from zsh_compat.zsh
# Behaviour here is identical to the pre-compat aliases: unchanged on macOS.

typeset -g CACHE_ROOT="$HOME/Library/Caches"
typeset -g SUPPORT_ROOT="$HOME/Library/Application Support"
typeset -g LOG_ROOT="$HOME/Library/Logs"

_iface()       { route get default 2>/dev/null | awk '/interface:/{print $2}'; }
_local_ip()    { ipconfig getifaddr "$(_iface)" 2>/dev/null || echo 'n/a'; }
_gateway()     { route get default 2>/dev/null | awk '/gateway: /{print $2}'; }
_open_file()   { open "$@"; }
_lock_file()   { sudo chflags uchg "$1"; }
_unlock_file() { sudo chflags nouchg "$1"; }
_cache_dir()   { echo "$HOME/Library/Caches"; }
_adb_path()    { echo "$HOME/Library/Android/sdk/platform-tools/adb"; }
_net_ifaces()  { ifconfig -a 2>/dev/null | awk '/^[a-z][a-z0-9]*:/{print $1}'; }
_list_ports()  { lsof -iTCP -sTCP:LISTEN -P -n; }
_pkg_install() { brew install "$@"; }
