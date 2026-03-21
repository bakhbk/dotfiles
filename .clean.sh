# Purpose:
# System memory & cache cleanup script.
# NOTE: Must be sourced in zsh — uses zsh-specific glob features (${~var}(N)).
# Usage: clean [--all] [--ram] [--brew] [--xcode] [--flutter] [--node] [--docker]
#              [--browsers] [--go] [--rust] [--python] [--dev] [--logs] [--caches] [--system]
#
# Examples:
#   clean --all
#   clean --ram --docker
#   clean --xcode --flutter
#   clean --go --rust --python

clean() {
  if [[ -z "$ZSH_VERSION" ]]; then
    echo "⚠️  clean requires zsh. Source this file in zsh, not sh/bash."
    return 1
  fi

  local do_ram=0 do_brew=0 do_xcode=0 do_flutter=0 do_node=0
  local do_docker=0 do_browsers=0 do_go=0 do_rust=0 do_python=0
  local do_dev=0 do_logs=0 do_caches=0 do_system=0

  if [[ $# -eq 0 ]]; then
    echo "Usage: clean [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all        Run all cleanups"
    echo "  --ram        Free inactive RAM (sudo purge)"
    echo "  --brew       Homebrew cleanup + autoremove"
    echo "  --xcode      Xcode DerivedData, DeviceSupport, sim runtimes (sudo), CocoaPods"
    echo "  --flutter    Flutter build/, pub-cache, Gradle, Android caches"
    echo "  --node       node_modules (rclean), npm/yarn/pnpm cache"
    echo "  --docker     Docker system + image + volume + builder prune"
    echo "  --browsers   Chrome, Firefox, Safari, Arc, Cursor, Yandex caches"
    echo "  --go         Go build/test cache (~/.cache/go-build)"
    echo "  --rust       Cargo registry & git db cache"
    echo "  --python     uv, pip, pyenv, Poetry caches"
    echo "  --dev        Dev tool caches: aider, Neovim, Ollama, .llm, Cline, etc."
    echo "  --logs       App logs in ~/Library/Logs (>7 days old)"
    echo "  --caches     ~/Library/Caches for heavy apps (JetBrains, VSCode, etc.)"
    echo "  --system     DNS flush, font cache, Trash, Time Machine snapshots (sudo)"
    return 0
  fi

  for arg in "$@"; do
    case "$arg" in
      --all)      do_ram=1; do_brew=1; do_xcode=1; do_flutter=1; do_node=1; do_docker=1
                  do_browsers=1; do_go=1; do_rust=1; do_python=1
                  do_dev=1; do_logs=1; do_caches=1; do_system=1 ;;
      --ram)      do_ram=1 ;;
      --brew)     do_brew=1 ;;
      --xcode)    do_xcode=1 ;;
      --flutter)  do_flutter=1 ;;
      --node)     do_node=1 ;;
      --docker)   do_docker=1 ;;
      --browsers) do_browsers=1 ;;
      --go)       do_go=1 ;;
      --rust)     do_rust=1 ;;
      --python)   do_python=1 ;;
      --dev)      do_dev=1 ;;
      --logs)     do_logs=1 ;;
      --caches)   do_caches=1 ;;
      --system)   do_system=1 ;;
      *)
        echo "Unknown option: $arg"
        echo "Run 'clean' with no arguments to see usage."
        return 1
        ;;
    esac
  done

  # Pre-cache sudo credentials so parallel sudo calls don't prompt multiple times
  if [[ $do_ram -eq 1 || $do_xcode -eq 1 || $do_system -eq 1 ]]; then
    sudo -v || { echo "⚠️  sudo required for --ram / --xcode / --system"; return 1; }
  fi

  local _tmp
  _tmp=$(mktemp -d)
  local _pids=() _outs=()

  # ── RAM ──────────────────────────────────────────────────────────────────
  if [[ $do_ram -eq 1 ]]; then
    local _o="$_tmp/01_ram"; _outs+=("$_o")
    {
      echo "\n🧠 Freeing inactive RAM..."
      sudo -n purge && echo "  ✓ purge done"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Homebrew ──────────────────────────────────────────────────────────────
  if [[ $do_brew -eq 1 ]]; then
    local _o="$_tmp/02_brew"; _outs+=("$_o")
    {
      echo "\n🍺 Homebrew cleanup..."
      brew cleanup --prune=all 2>/dev/null && echo "  ✓ brew cleanup done"
      brew autoremove 2>/dev/null && echo "  ✓ brew orphan formulae removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Xcode ────────────────────────────────────────────────────────────────
  if [[ $do_xcode -eq 1 ]]; then
    local _o="$_tmp/03_xcode"; _outs+=("$_o")
    {
      echo "\n📱 Xcode cleanup..."
      rm -rf ~/Library/Developer/Xcode/DerivedData 2>/dev/null && echo "  ✓ DerivedData removed"
      rm -rf ~/Library/Developer/Xcode/iOS\ DeviceSupport 2>/dev/null && echo "  ✓ iOS DeviceSupport removed"
      rm -rf ~/Library/Developer/Xcode/watchOS\ DeviceSupport 2>/dev/null && echo "  ✓ watchOS DeviceSupport removed"
      rm -rf ~/Library/Developer/CoreSimulator/Caches 2>/dev/null && echo "  ✓ User CoreSimulator caches removed"
      xcrun simctl shutdown all 2>/dev/null && echo "  ✓ simulators shut down"
      xcrun simctl erase all 2>/dev/null && echo "  ✓ simulators erased"
      # System-level simulator runtimes — the big ones (up to 16G in /Library/Developer)
      xcrun simctl runtime delete all 2>/dev/null && echo "  ✓ simulator runtimes deleted"
      sudo -n rm -rf /Library/Developer/CoreSimulator/Caches 2>/dev/null && echo "  ✓ System CoreSimulator caches removed"
      pod cache clean --all 2>/dev/null && echo "  ✓ CocoaPods cache cleaned"
      rm -rf ~/Library/Caches/CocoaPods 2>/dev/null && echo "  ✓ CocoaPods Library cache removed"
      rm -rf ~/.swiftpm/cache 2>/dev/null && echo "  ✓ SwiftPM cache removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Flutter / Dart / Android ──────────────────────────────────────────────
  if [[ $do_flutter -eq 1 ]]; then
    local _o="$_tmp/04_flutter"; _outs+=("$_o")
    {
      echo "\n🐦 Flutter/Dart/Android cleanup..."
      rm -rf ~/.pub-cache 2>/dev/null && echo "  ✓ .pub-cache removed"
      rm -rf ~/.dart_tool 2>/dev/null && echo "  ✓ .dart_tool removed"
      rm -rf ~/.gradle/caches 2>/dev/null && echo "  ✓ Gradle caches removed"
      rm -rf ~/.android/cache 2>/dev/null && echo "  ✓ Android SDK cache removed"
      rm -rf ~/Library/Caches/Google/AndroidStudio* 2>/dev/null && echo "  ✓ Android Studio caches removed"
      fclean 2>/dev/null && echo "  ✓ flutter project build/ dirs removed"
      if command -v fvm &>/dev/null; then
        fvm flutter pub cache clean 2>/dev/null && echo "  ✓ fvm pub cache cleaned"
      elif command -v flutter &>/dev/null; then
        flutter pub cache clean 2>/dev/null && echo "  ✓ flutter pub cache cleaned"
      fi
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Node / npm / yarn / pnpm ──────────────────────────────────────────────
  if [[ $do_node -eq 1 ]]; then
    local _o="$_tmp/05_node"; _outs+=("$_o")
    {
      echo "\n📦 Node/npm/yarn/pnpm cleanup..."
      npm cache clean --force 2>/dev/null && echo "  ✓ npm cache cleaned"
      rclean 2>/dev/null && echo "  ✓ node_modules dirs removed"
      rm -rf ~/.npm/_logs/*.log 2>/dev/null && echo "  ✓ npm logs removed"
      if command -v yarn &>/dev/null; then
        yarn cache clean 2>/dev/null && echo "  ✓ yarn cache cleaned"
      fi
      rm -rf ~/.cache/yarn 2>/dev/null && echo "  ✓ yarn cache dir removed"
      if command -v pnpm &>/dev/null; then
        pnpm store prune 2>/dev/null && echo "  ✓ pnpm store pruned"
      fi
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Docker ───────────────────────────────────────────────────────────────
  if [[ $do_docker -eq 1 ]]; then
    local _o="$_tmp/06_docker"; _outs+=("$_o")
    {
      echo "\n🐳 Docker cleanup..."
      docker system prune -f 2>/dev/null && echo "  ✓ docker system pruned"
      docker image prune -a -f 2>/dev/null && echo "  ✓ docker images pruned"
      docker volume prune -f 2>/dev/null && echo "  ✓ docker volumes pruned"
      docker builder prune -a -f 2>/dev/null && echo "  ✓ docker builder cache pruned"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Browsers ─────────────────────────────────────────────────────────────
  if [[ $do_browsers -eq 1 ]]; then
    local _o="$_tmp/07_browsers"; _outs+=("$_o")
    {
      echo "\n🌐 Browser caches cleanup..."
      rm -rf ~/Library/Caches/Google/Chrome 2>/dev/null && echo "  ✓ Chrome Caches removed"
      rm -rf ~/Library/Application\ Support/Google/Chrome/Default/Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Google/Chrome/Default/Code\ Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Google/Chrome/Default/GPUCache 2>/dev/null && echo "  ✓ Chrome profile caches removed"
      rm -rf ~/Library/Caches/MediaAnalysis 2>/dev/null && echo "  ✓ MediaAnalysis cache removed"
      rm -rf ~/Library/Caches/com.apple.mediaanalysisd 2>/dev/null
      rm -rf ~/Library/Caches/ru.yandex.* 2>/dev/null && echo "  ✓ Yandex caches removed"
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/Code\ Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/GPUCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/DawnWebGPUCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/DawnGraphiteCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/Default/TurboAppCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/ShaderCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/GraphiteDawnCache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Yandex/YandexBrowser/GrShaderCache 2>/dev/null && echo "  ✓ Yandex App Support caches removed"
      rm -rf ~/Library/Caches/Firefox 2>/dev/null && echo "  ✓ Firefox cache removed"
      rm -rf ~/Library/Caches/com.apple.Safari 2>/dev/null && echo "  ✓ Safari cache removed"
      rm -rf ~/Library/Safari/LocalStorage 2>/dev/null && echo "  ✓ Safari LocalStorage removed"
      rm -rf ~/Library/Application\ Support/Cursor/Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Cursor/Code\ Cache 2>/dev/null
      rm -rf ~/Library/Application\ Support/Cursor/GPUCache 2>/dev/null && echo "  ✓ Cursor caches removed"
      rm -rf ~/Library/Caches/company.thebrowser.Browser 2>/dev/null && echo "  ✓ Arc cache removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Go ───────────────────────────────────────────────────────────────────
  if [[ $do_go -eq 1 ]]; then
    local _o="$_tmp/08_go"; _outs+=("$_o")
    {
      echo "\n🐹 Go cleanup..."
      if command -v go &>/dev/null; then
        go clean -cache 2>/dev/null && echo "  ✓ Go build cache cleaned"
        go clean -testcache 2>/dev/null && echo "  ✓ Go test cache cleaned"
      fi
      rm -rf ~/.cache/go-build 2>/dev/null && echo "  ✓ ~/.cache/go-build removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Rust / Cargo ─────────────────────────────────────────────────────────
  if [[ $do_rust -eq 1 ]]; then
    local _o="$_tmp/09_rust"; _outs+=("$_o")
    {
      echo "\n🦀 Rust/Cargo cleanup..."
      rm -rf ~/.cargo/registry/cache 2>/dev/null && echo "  ✓ Cargo registry cache removed"
      rm -rf ~/.cargo/git/db 2>/dev/null && echo "  ✓ Cargo git db removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Python ───────────────────────────────────────────────────────────────
  if [[ $do_python -eq 1 ]]; then
    local _o="$_tmp/10_python"; _outs+=("$_o")
    {
      echo "\n🐍 Python cleanup..."
      if command -v uv &>/dev/null; then
        uv cache clean 2>/dev/null && echo "  ✓ uv cache cleaned"
      fi
      rm -rf ~/.cache/uv 2>/dev/null && echo "  ✓ ~/.cache/uv removed"
      rm -rf ~/.cache/pip 2>/dev/null && echo "  ✓ pip cache removed"
      rm -rf ~/.pyenv/cache 2>/dev/null && echo "  ✓ pyenv download cache removed"
      rm -rf ~/Library/Caches/pypoetry 2>/dev/null && echo "  ✓ Poetry cache removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Dev tools ────────────────────────────────────────────────────────────
  if [[ $do_dev -eq 1 ]]; then
    local _o="$_tmp/11_dev"; _outs+=("$_o")
    {
      echo "\n🔧 Dev tools cleanup..."
      rm -rf ~/.cache/aider 2>/dev/null && echo "  ✓ aider cache removed"
      rm -rf ~/.aider* 2>/dev/null && echo "  ✓ .aider* removed"
      rm -rf ~/.llm 2>/dev/null && echo "  ✓ .llm removed"
      rm -rf ~/Library/Application\ Support/io.datasette.llm 2>/dev/null && echo "  ✓ datasette llm removed"
      rm -rf ~/.cocoapods 2>/dev/null && echo "  ✓ .cocoapods removed"
      rm -rf ~/.cline ~/.clinerc 2>/dev/null && echo "  ✓ .cline removed"
      rm -rf ~/.zcompdump* 2>/dev/null && echo "  ✓ zsh completion cache removed"
      rm -rf ~/.local/share/nvim/swap 2>/dev/null && echo "  ✓ Neovim swap removed"
      rm -rf ~/.local/share/nvim/undo 2>/dev/null && echo "  ✓ Neovim undo removed"
      rm -rf ~/.local/share/nvim/lazy/stats 2>/dev/null && echo "  ✓ Neovim lazy stats removed"
      rm -rf ~/.ollama/logs 2>/dev/null && echo "  ✓ Ollama logs removed"
      rm -rf ~/.cache/firebase 2>/dev/null && echo "  ✓ Firebase CLI cache removed"
      rm -rf ~/.cache/gem 2>/dev/null && echo "  ✓ Ruby gem cache removed"
      rm -rf ~/.cache/nvim 2>/dev/null && echo "  ✓ Neovim cache dir removed"
      rm -rf ~/.cache/mesa_shader_cache 2>/dev/null && echo "  ✓ Mesa shader cache removed"
      clean_temp 2>/dev/null && echo "  ✓ clean_temp done"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Logs ─────────────────────────────────────────────────────────────────
  if [[ $do_logs -eq 1 ]]; then
    local _o="$_tmp/12_logs"; _outs+=("$_o")
    {
      echo "\n📋 Logs cleanup..."
      rm -rf ~/Library/Logs/CoreSimulator 2>/dev/null && echo "  ✓ CoreSimulator logs removed"
      find ~/Library/Logs -name "*.log" -mtime +7 -delete 2>/dev/null && echo "  ✓ App logs older than 7 days removed"
      rm -rf ~/.npm/_logs/*.log 2>/dev/null && echo "  ✓ npm logs removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── App Caches (~/Library/Caches) ─────────────────────────────────────────
  if [[ $do_caches -eq 1 ]]; then
    local _o="$_tmp/13_caches"; _outs+=("$_o")
    {
      echo "\n🗂  App caches cleanup..."
      local caches_dir=~/Library/Caches
      local app_caches=(
        "com.jetbrains.*"
        "JetBrains"
        "com.microsoft.VSCode"
        "com.todesktop.*"
        "dev.warp.*"
        "com.obsidian.*"
        "com.postmanlabs.*"
        "com.google.*"
        "asc.onlyoffice.*"
        "company.thebrowser.Browser"
        "com.tinyspeck.slackmacgap"
        "ru.keepcoder.Telegram"
        "com.apple.Safari"
      )
      for pattern in "${app_caches[@]}"; do
        rm -rf ${caches_dir}/${~pattern}(N) 2>/dev/null
      done
      echo "  ✓ App caches cleaned (JetBrains, VSCode, Warp, Obsidian, Postman, Google, OnlyOffice, Arc, Slack, Telegram, Safari)"
      # VSCode Application Support caches (CachedExtensionVSIXs alone ~375 MB)
      local vscode_as=~/Library/Application\ Support/Code
      rm -rf "$vscode_as/Cache" "$vscode_as/CachedData" "$vscode_as/CachedExtensionVSIXs" \
             "$vscode_as/CachedProfilesData" "$vscode_as/Code Cache" \
             "$vscode_as/GPUCache" "$vscode_as/logs" 2>/dev/null && echo "  ✓ VSCode Application Support caches removed"
      # Remove workspaceStorage entries not accessed for >30 days
      find "$vscode_as/User/workspaceStorage" -maxdepth 1 -mindepth 1 -type d -atime +30 -exec rm -rf {} + 2>/dev/null && echo "  ✓ VSCode stale workspaceStorage removed"
      # Zed editor hang traces
      rm -rf ~/Library/Application\ Support/Zed/hang_traces 2>/dev/null && echo "  ✓ Zed hang traces removed"
      # cloud-code extension CLI binary (auto re-downloaded on next use)
      rm -rf ~/Library/Application\ Support/cloud-code/cloudcode_cli 2>/dev/null && echo "  ✓ cloud-code CLI cache removed"
      # VSCode WebStorage (IndexedDB / localStorage for extensions)
      rm -rf "$vscode_as/WebStorage" 2>/dev/null && echo "  ✓ VSCode WebStorage removed"
      # Google Updater CRX cache — Chrome auto-refills on next update check
      rm -rf ~/Library/Application\ Support/Google/GoogleUpdater/crx_cache 2>/dev/null && echo "  ✓ GoogleUpdater CRX cache removed"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── System ───────────────────────────────────────────────────────────────
  if [[ $do_system -eq 1 ]]; then
    local _o="$_tmp/14_system"; _outs+=("$_o")
    {
      echo "\n⚙️  System cleanup..."
      sudo -n dscacheutil -flushcache 2>/dev/null && sudo -n killall -HUP mDNSResponder 2>/dev/null && echo "  ✓ DNS cache flushed"
      sudo -n atsutil databases -remove 2>/dev/null && echo "  ✓ Font cache removed"
      osascript -e 'tell application "Finder" to empty trash' 2>/dev/null && echo "  ✓ Trash emptied"
      sudo -n rm -rf /private/var/log/asl/*.asl 2>/dev/null && echo "  ✓ ASL system logs removed"
      # Time Machine local snapshots — hidden reserved space, can be several GB
      sudo -n tmutil deletelocalsnapshots / 2>/dev/null && echo "  ✓ Time Machine local snapshots deleted"
      # Unified system log database (~2-3 GB, rebuilt automatically by logd)
      sudo -n log erase --all 2>/dev/null && echo "  ✓ Unified log database erased"
    } >"$_o" 2>&1 &
    _pids+=($!)
  fi

  # ── Wait & print ──────────────────────────────────────────────────────────
  echo "⏳ Running ${#_pids[@]} cleanup tasks in parallel..."
  local _failed=0
  for pid in "${_pids[@]}"; do
    wait "$pid" || (( _failed++ ))
  done

  for out in "${_outs[@]}"; do
    [[ -f "$out" ]] && cat "$out"
  done
  rm -rf "$_tmp"

  echo "\n✅ Done (${#_pids[@]} tasks, $_failed failed)."
}