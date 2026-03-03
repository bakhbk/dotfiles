# Purpose:
# System memory & cache cleanup script.
# Usage: clean [--all] [--ram] [--brew] [--xcode] [--flutter] [--node] [--docker] [--browsers] [--dev] [--caches]
#
# Examples:
#   clean --all
#   clean --ram --docker
#   clean --xcode --flutter

clean() {
  local do_ram=0 do_brew=0 do_xcode=0 do_flutter=0 do_node=0
  local do_docker=0 do_browsers=0 do_dev=0 do_caches=0

  if [[ $# -eq 0 ]]; then
    echo "Usage: clean [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all        Run all cleanups"
    echo "  --ram        Free inactive RAM (sudo purge)"
    echo "  --brew       Homebrew cleanup"
    echo "  --xcode      Xcode DerivedData, simulators, CocoaPods cache"
    echo "  --flutter    Flutter build/, pub-cache, Gradle caches"
    echo "  --node       node_modules (rclean), npm cache"
    echo "  --docker     Docker system + image prune"
    echo "  --browsers   Chrome, Firefox, Cursor, Yandex caches"
    echo "  --dev        Dev tool caches: aider, .gradle, .dart_tool, .pub-cache, etc."
    echo "  --caches     ~/Library/Caches for heavy apps (JetBrains, VSCode, etc.)"
    return 0
  fi

  for arg in "$@"; do
    case "$arg" in
      --all)      do_ram=1; do_brew=1; do_xcode=1; do_flutter=1; do_node=1; do_docker=1; do_browsers=1; do_dev=1; do_caches=1 ;;
      --ram)      do_ram=1 ;;
      --brew)     do_brew=1 ;;
      --xcode)    do_xcode=1 ;;
      --flutter)  do_flutter=1 ;;
      --node)     do_node=1 ;;
      --docker)   do_docker=1 ;;
      --browsers) do_browsers=1 ;;
      --dev)      do_dev=1 ;;
      --caches)   do_caches=1 ;;
      *)
        echo "Unknown option: $arg"
        echo "Run 'clean' with no arguments to see usage."
        return 1
        ;;
    esac
  done

  # ── RAM ──────────────────────────────────────────────────────────────────
  if [[ $do_ram -eq 1 ]]; then
    echo "\n🧠 Freeing inactive RAM..."
    sudo purge && echo "  ✓ purge done"
  fi

  # ── Homebrew ──────────────────────────────────────────────────────────────
  if [[ $do_brew -eq 1 ]]; then
    echo "\n🍺 Homebrew cleanup..."
    brew cleanup --prune=all 2>/dev/null && echo "  ✓ brew cleanup done"
  fi

  # ── Xcode ────────────────────────────────────────────────────────────────
  if [[ $do_xcode -eq 1 ]]; then
    echo "\n📱 Xcode cleanup..."
    rm -rf ~/Library/Developer/Xcode/DerivedData 2>/dev/null && echo "  ✓ DerivedData removed"
    xcrun simctl shutdown all 2>/dev/null && echo "  ✓ simulators shut down"
    xcrun simctl erase all 2>/dev/null && echo "  ✓ simulators erased"
    pod cache clean --all 2>/dev/null && echo "  ✓ CocoaPods cache cleaned"
    rm -rf ~/Library/Caches/com.apple.mail 2>/dev/null
  fi

  # ── Flutter / Dart ────────────────────────────────────────────────────────
  if [[ $do_flutter -eq 1 ]]; then
    echo "\n🐦 Flutter/Dart cleanup..."
    rm -rf ~/.pub-cache 2>/dev/null && echo "  ✓ .pub-cache removed"
    rm -rf ~/.dart_tool 2>/dev/null && echo "  ✓ .dart_tool removed"
    rm -rf ~/.gradle/caches 2>/dev/null && echo "  ✓ Gradle caches removed"
    fclean 2>/dev/null && echo "  ✓ flutter project build/ dirs removed"
    if command -v fvm &>/dev/null; then
      fvm flutter pub cache clean 2>/dev/null && echo "  ✓ fvm pub cache cleaned"
    elif command -v flutter &>/dev/null; then
      flutter pub cache clean 2>/dev/null && echo "  ✓ flutter pub cache cleaned"
    fi
  fi

  # ── Node / npm ────────────────────────────────────────────────────────────
  if [[ $do_node -eq 1 ]]; then
    echo "\n📦 Node/npm cleanup..."
    npm cache clean --force 2>/dev/null && echo "  ✓ npm cache cleaned"
    rclean 2>/dev/null && echo "  ✓ node_modules dirs removed"
    rm -rf ~/.npm/_logs/*.log 2>/dev/null && echo "  ✓ npm logs removed"
  fi

  # ── Docker ───────────────────────────────────────────────────────────────
  if [[ $do_docker -eq 1 ]]; then
    echo "\n🐳 Docker cleanup..."
    docker system prune -f 2>/dev/null && echo "  ✓ docker system pruned"
    docker image prune -a -f 2>/dev/null && echo "  ✓ docker images pruned"
  fi

  # ── Browsers ─────────────────────────────────────────────────────────────
  if [[ $do_browsers -eq 1 ]]; then
    echo "\n🌐 Browser caches cleanup..."
    rm -rf ~/Library/Application\ Support/Google/Chrome/ 2>/dev/null && echo "  ✓ Chrome App Support removed"
    rm -rf ~/Library/Caches/Google/Chrome/ 2>/dev/null && echo "  ✓ Chrome Caches removed"
    rm -rf ~/Library/Preferences/com.google.Chrome.plist 2>/dev/null
    rm -rf ~/Library/Saved\ Application\ State/com.google.Chrome.savedState/ 2>/dev/null
    rm -rf ~/Library/Caches/MediaAnalysis 2>/dev/null && echo "  ✓ MediaAnalysis cache removed"
    rm -rf ~/Library/Caches/com.apple.mediaanalysisd 2>/dev/null
    rm -rf ~/Library/Caches/ru.yandex.* 2>/dev/null && echo "  ✓ Yandex caches removed"
    rm -rf ~/Library/Caches/Firefox 2>/dev/null && echo "  ✓ Firefox cache removed"
  fi

  # ── Dev tools ────────────────────────────────────────────────────────────
  if [[ $do_dev -eq 1 ]]; then
    echo "\n🔧 Dev tools cleanup..."
    rm -rf ~/.cache/aider 2>/dev/null && echo "  ✓ aider cache removed"
    rm -rf ~/.aider* 2>/dev/null && echo "  ✓ .aider* removed"
    rm -rf ~/.cache/pip 2>/dev/null && echo "  ✓ pip cache removed"
    rm -rf ~/.llm 2>/dev/null && echo "  ✓ .llm removed"
    rm -rf "~/Library/Application Support/io.datasette.llm" 2>/dev/null
    rm -rf ~/.cocoapods 2>/dev/null && echo "  ✓ .cocoapods removed"
    rm -rf ~/.cline ~/.clinerc 2>/dev/null && echo "  ✓ .cline removed"
    rm -rf ~/.gradle/caches 2>/dev/null && echo "  ✓ Gradle caches removed"
    rm -rf ~/.dart_tool 2>/dev/null
    rm -rf ~/.zcompdump* 2>/dev/null && echo "  ✓ zsh completion cache removed"
    clean_temp 2>/dev/null && echo "  ✓ clean_temp done"
  fi

  # ── App Caches (~/Library/Caches) ─────────────────────────────────────────
  if [[ $do_caches -eq 1 ]]; then
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
    )
    for pattern in "${app_caches[@]}"; do
      rm -rf ${caches_dir}/${~pattern} 2>/dev/null
    done
    echo "  ✓ App caches cleaned (JetBrains, VSCode, Warp, Obsidian, Postman, Google, OnlyOffice)"
  fi

  echo "\n✅ Done."
}
