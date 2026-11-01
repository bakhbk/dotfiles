#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

PROG_NAME="vpn_install_connect.sh"

usage() {
  cat <<-USAGE
Usage: $PROG_NAME [--stop] <config.ovpn>

Installs OpenVPN (if missing) on Linux or macOS and connects using provided .ovpn file.

Options:
  --stop        Stop an active VPN started by this script (uses stored pid file).

Examples:
  $PROG_NAME /path/to/config.ovpn
  $PROG_NAME --stop /path/to/config.ovpn

Notes:
  - The script uses `openvpn` CLI. On macOS it will attempt an unattended Homebrew install if missing.
  - This script starts OpenVPN with `--daemon` and writes pid/log into /tmp/openvpn-<configname>.*
USAGE
}

if [ $# -eq 0 ]; then
  usage
  exit 1
fi

AUTO_BREW=1
STOP=0
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --stop)
      STOP=1; shift;;
    -h|--help)
      usage; exit 0;;
    --)
      shift; while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done; break;;
    -*|--*)
      echo "Unknown option: $1" >&2; usage; exit 2;;
    *)
      ARGS+=("$1"); shift;;
  esac
done

if [ ${#ARGS[@]} -lt 1 ]; then
  echo "Missing .ovpn config file" >&2
  usage; exit 2
fi

CONFIG="${ARGS[0]}"
if [ ! -f "$CONFIG" ]; then
  echo "Config file not found: $CONFIG" >&2
  exit 3
fi

OS_TYPE="$(uname -s)"

log_and_exit() {
  echo "$*" >&2
  exit 1
}

ensure_openvpn() {
  if command -v openvpn >/dev/null 2>&1; then
    return 0
  fi
  case "$OS_TYPE" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        echo "Installing openvpn via Homebrew..."
        brew install openvpn || log_and_exit "brew install openvpn failed"
      else
        echo "Homebrew not found — attempting unattended installer (NONINTERACTIVE=1)."
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || log_and_exit "Homebrew install failed"
        # Ensure brew is on PATH for current shell; handle both Apple Silicon and Intel locations.
        if [ -x "/opt/homebrew/bin/brew" ]; then
          eval "$(/opt/homebrew/bin/brew shellenv)" || true
        elif [ -x "/usr/local/bin/brew" ]; then
          eval "$(/usr/local/bin/brew shellenv)" || true
        else
          # try command -v as a fallback
          if command -v brew >/dev/null 2>&1; then
            eval "$(brew shellenv)" || true
          fi
        fi
        brew install openvpn || log_and_exit "brew install openvpn failed after installing Homebrew"
      fi
      ;;
    Linux)
      echo "Detecting package manager to install openvpn..."
      if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y openvpn || log_and_exit "apt-get install openvpn failed"
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y openvpn || log_and_exit "dnf install openvpn failed"
      elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y openvpn || log_and_exit "yum install openvpn failed"
      elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Syu --noconfirm openvpn || log_and_exit "pacman install openvpn failed"
      else
        log_and_exit "Unsupported Linux distribution. Please install 'openvpn' manually."
      fi
      ;;
    *)
      log_and_exit "Unsupported OS: $OS_TYPE"
      ;;
  esac
}

pid_and_log_for() {
  local cfg="$1"
  local name
  name="$(basename "$cfg" .ovpn | tr ' ' '_' )"
  echo "/tmp/openvpn-${name}.pid|/tmp/openvpn-${name}.log"
}

start_vpn() {
  local cfg="$1"
  local pidfile log
  IFS='|' read -r pidfile log <<< "$(pid_and_log_for "$cfg")"
  if [ -f "$pidfile" ]; then
    echo "PID file exists: $pidfile (VPN may already be running). Use --stop to stop it or remove the pid file manually." >&2
    return 0
  fi
  echo "Starting OpenVPN... (config: $cfg)"
  sudo openvpn --config "$cfg" --daemon --writepid "$pidfile" --log "$log" || log_and_exit "Failed to launch openvpn"
  sleep 1
  if [ -f "$pidfile" ]; then
    echo "OpenVPN started. PID: $(cat "$pidfile"). Log: $log"
  else
    echo "OpenVPN failed to start. See $log for details." >&2
    [ -f "$log" ] && tail -n +1 "$log" >&2
    exit 5
  fi
}

stop_vpn() {
  local cfg="$1"
  local pidfile log pid
  IFS='|' read -r pidfile log <<< "$(pid_and_log_for "$cfg")"
  if [ ! -f "$pidfile" ]; then
    echo "No pid file found ($pidfile). Nothing to stop."
    return 0
  fi
  pid=$(cat "$pidfile" 2>/dev/null || true)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping OpenVPN (pid $pid)..."
    sudo kill "$pid" || sudo kill -TERM "$pid" || echo "Failed to kill process $pid"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      echo "Process still alive. You may need to stop it manually." >&2
    else
      echo "Stopped. Removing pid file."
      sudo rm -f "$pidfile" 2>/dev/null || true
    fi
  else
    echo "Process $pid not running. Removing stale pid file.";
    sudo rm -f "$pidfile" 2>/dev/null || true
  fi
}

# Main flow
ensure_openvpn
if [ "$STOP" -eq 1 ]; then
  stop_vpn "$CONFIG"
  exit 0
fi
start_vpn "$CONFIG"

exit 0
