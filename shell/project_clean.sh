#!/usr/bin/env zsh
# ──────────────────────────────────────────────────────────────────────────────
# project_clean.sh — Universal project-level cleanup
#
# Finds projects by marker files and removes their build/cache artifacts.
# Safe to run from any directory — operates on ~/own_projects/ and ~/work/.
#
# Usage:
#   source ~/dotfiles/shell/project_clean.sh       # defines pclean()
#   pclean                                           # dry-run (default)
#   pclean --apply                                   # actually delete
#
# Options:
#   --dry-run   Show what would be cleaned (default)
#   --apply     Actually delete files
#   --help      Show this help
# ──────────────────────────────────────────────────────────────────────────────

pclean() {
  local DRY_RUN=1 APPLY=0

  # Argument parsing
  local TARGET_DIRS=()
  local _next=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)  DRY_RUN=1; APPLY=0; _next=0 ;;
      --apply)    DRY_RUN=0; APPLY=1; _next=0 ;;
      --help)     show_help; return 0 ;;
      --target)
        shift; [[ $# -gt 0 ]] && TARGET_DIRS=("$1")
        ;;
      *)          echo "Unknown option: $1"; echo "Run 'pclean --help' for usage."; return 1 ;;
    esac
    shift
  done

  # Safety
  if [[ "$HOME" == "/" ]]; then
    echo "ERROR: HOME is /. Aborting."
    return 1
  fi

  local DIRS
  if [[ ${#TARGET_DIRS[@]} -gt 0 ]]; then
    DIRS=("${TARGET_DIRS[@]}")
  else
    DIRS=("$HOME/own_projects" "$HOME/work")
  fi
  local total_items=0 total_size=0
  local tmpdir
  tmpdir=$(mktemp -d)

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "=== project_clean — DRY RUN ==="
  else
    echo "=== project_clean — APPLYING ==="
  fi

  for base_dir in "${DIRS[@]}"; do
    if [[ ! -d "$base_dir" ]]; then
      echo "  ⚠ $base_dir not found, skipping"
      continue
    fi

    echo ""
    echo "─────────────────────────────────────────"
    echo "Scanning: $base_dir"
    echo "─────────────────────────────────────────"

    # ── 1. Flutter / Dart ──────────────────────────────────────────────────
    echo ""
    echo "[Flutter/Dart]"

    local flutter_projects
    flutter_projects=$(find "$base_dir" -name 'pubspec.yaml' -type f 2>/dev/null | grep -v '.symlinks' | xargs -I{} dirname {} 2>/dev/null)

    local flutter_count=0
    for proj in $flutter_projects; do
      [[ -z "$proj" ]] && continue
      (( flutter_count++ ))
      local rel="${proj#$base_dir/}"

      # .dart_tool/
      if [[ -d "$proj/.dart_tool" ]]; then
        local sz
        sz=$(du -sm "$proj/.dart_tool" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.dart_tool       ${sz}M"
        else
          rm -rf "$proj/.dart_tool" && echo "  ✓ $rel/.dart_tool removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # build/
      if [[ -d "$proj/build" ]]; then
        local sz
        sz=$(du -sm "$proj/build" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/build           ${sz}M"
        else
          rm -rf "$proj/build" && echo "  ✓ $rel/build removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # .fvm/
      if [[ -d "$proj/.fvm" ]]; then
        local sz
        sz=$(du -sm "$proj/.fvm" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.fvm            ${sz}M"
        else
          rm -rf "$proj/.fvm" && echo "  ✓ $rel/.fvm removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # android/.gradle
      if [[ -d "$proj/android/.gradle" ]]; then
        local sz
        sz=$(du -sm "$proj/android/.gradle" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/android/.gradle  ${sz}M"
        else
          rm -rf "$proj/android/.gradle" && echo "  ✓ $rel/android/.gradle removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # android/.kotlin
      if [[ -d "$proj/android/.kotlin" ]]; then
        local sz
        sz=$(du -sm "$proj/android/.kotlin" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/android/.kotlin  ${sz}M"
        else
          rm -rf "$proj/android/.kotlin" && echo "  ✓ $rel/android/.kotlin removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # android/build
      if [[ -d "$proj/android/build" ]]; then
        local sz
        sz=$(du -sm "$proj/android/build" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/android/build    ${sz}M"
        else
          rm -rf "$proj/android/build" && echo "  ✓ $rel/android/build removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # .cxx (Flutter native CMake)
      if [[ -d "$proj/.cxx" ]]; then
        local sz
        sz=$(du -sm "$proj/.cxx" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.cxx             ${sz}M"
        else
          rm -rf "$proj/.cxx" && echo "  ✓ $rel/.cxx removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi
    done

    # iOS/macOS XCode Build/Intermediates — separate loop (can't nest in above)
    for proj in $flutter_projects; do
      [[ -z "$proj" ]] && continue
      local rel="${proj#$base_dir/}"

      if [[ -d "$proj/ios/build" ]]; then
        find "$proj/ios/build" -path '*/Build/Intermediates.noindex' -type d 2>/dev/null > "$tmpdir/xcode_ios"
        while read -r xcode_dir; do
          local sz
          sz=$(du -sm "$xcode_dir" 2>/dev/null | cut -f1)
          if [[ $DRY_RUN -eq 1 ]]; then
            echo "  ⏭ $rel/ios/.../Intermediates  ${sz}M"
          else
            rm -rf "$xcode_dir" && echo "  ✓ $rel/ios/.../Intermediates removed"
          fi
          (( total_items++ ))
          (( total_size += sz ))
        done < "$tmpdir/xcode_ios"
      fi

      if [[ -d "$proj/macos/build" ]]; then
        find "$proj/macos/build" -path '*/Build/Intermediates.noindex' -type d 2>/dev/null > "$tmpdir/xcode_macos"
        while read -r xcode_dir; do
          local sz
          sz=$(du -sm "$xcode_dir" 2>/dev/null | cut -f1)
          if [[ $DRY_RUN -eq 1 ]]; then
            echo "  ⏭ $rel/macos/.../Intermediates  ${sz}M"
          else
            rm -rf "$xcode_dir" && echo "  ✓ $rel/macos/.../Intermediates removed"
          fi
          (( total_items++ ))
          (( total_size += sz ))
        done < "$tmpdir/xcode_macos"
      fi
    done

    if [[ $flutter_count -eq 0 ]]; then
      echo "  (no Flutter projects found)"
    else
      echo "  → $flutter_count Flutter project(s) scanned"
    fi

    # ── 2. Node.js / npm / yarn / pnpm ──────────────────────────────────────
    echo ""
    echo "[Node.js]"

    local node_projects
    node_projects=$(find "$base_dir" -name 'package.json' -type f -not -path '*/node_modules/*' 2>/dev/null | xargs -I{} dirname {} 2>/dev/null | sort -u)

    for proj in $node_projects; do
      [[ -z "$proj" ]] && continue
      local rel="${proj#$base_dir/}"

      # node_modules/
      if [[ -d "$proj/node_modules" ]]; then
        local sz
        sz=$(du -sm "$proj/node_modules" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/node_modules   ${sz}M"
        else
          rm -rf "$proj/node_modules" && echo "  ✓ $rel/node_modules removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # .yarn/ (Yarn cache)
      if [[ -d "$proj/.yarn" ]]; then
        local sz
        sz=$(du -sm "$proj/.yarn" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.yarn          ${sz}M"
        else
          rm -rf "$proj/.yarn" && echo "  ✓ $rel/.yarn removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # dist/ (project-built JS bundles)
      if [[ -d "$proj/dist" ]]; then
        if ls "$proj/dist"/*.js "$proj/dist"/*.mjs "$proj/dist"/*.d.ts &>/dev/null; then
          local sz
          sz=$(du -sm "$proj/dist" 2>/dev/null | cut -f1)
          if [[ $DRY_RUN -eq 1 ]]; then
            echo "  ⏭ $rel/dist            ${sz}M"
          else
            rm -rf "$proj/dist" && echo "  ✓ $rel/dist removed"
          fi
          (( total_items++ ))
          (( total_size += sz ))
        fi
      fi

      # .next/ (Next.js), .nuxt/ (Nuxt), .svelte-kit/ (Svelte)
      for cache_dir in .next .nuxt .svelte-kit; do
        if [[ -d "$proj/$cache_dir" ]]; then
          local sz
          sz=$(du -sm "$proj/$cache_dir" 2>/dev/null | cut -f1)
          if [[ $DRY_RUN -eq 1 ]]; then
            echo "  ⏭ $rel/$cache_dir      ${sz}M"
          else
            rm -rf "$proj/$cache_dir" && echo "  ✓ $rel/$cache_dir removed"
          fi
          (( total_items++ ))
          (( total_size += sz ))
        fi
      done
    done
    echo "  → node_modules + JS build artifacts processed"

    # ── 3. Python ──────────────────────────────────────────────────────────
    echo ""
    echo "[Python]"

    local py_projects
    py_projects=$(find "$base_dir" \( -name 'pyproject.toml' -o -name 'setup.py' -o -name 'requirements.txt' \) -type f 2>/dev/null | xargs -I{} dirname {} 2>/dev/null | sort -u)

    for proj in $py_projects; do
      [[ -z "$proj" ]] && continue
      local rel="${proj#$base_dir/}"

      # __pycache__/ (recursive, skip site-packages)
      find "$proj" -name '__pycache__' -type d 2>/dev/null > "$tmpdir/pycache"
      while read -r pycache; do
        case "$pycache" in
          */.venv/lib/*|*/site-packages/*) continue ;;
        esac
        local sz
        sz=$(du -sm "$pycache" 2>/dev/null | cut -f1)
        local rpath="${pycache#$proj/}"
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/$rpath  ${sz}M"
        else
          rm -rf "$pycache" && echo "  ✓ $rel/$rpath removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      done < "$tmpdir/pycache"

      # .venv/ (skip Docker plugin Daemons — they re-download automatically)
      if [[ -d "$proj/.venv" ]]; then
        case "$proj" in
          *docker/volumes/plugin_daemon/*) continue ;;  # Docker plugins: re-downloaded automatically
        esac
        local sz
        sz=$(du -sm "$proj/.venv" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.venv          ${sz}M"
        else
          rm -rf "$proj/.venv" && echo "  ✓ $rel/.venv removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # .pytest_cache/
      if [[ -d "$proj/.pytest_cache" ]]; then
        local sz
        sz=$(du -sm "$proj/.pytest_cache" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.pytest_cache  ${sz}M"
        else
          rm -rf "$proj/.pytest_cache" && echo "  ✓ $rel/.pytest_cache removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # .ruff_cache/
      if [[ -d "$proj/.ruff_cache" ]]; then
        local sz
        sz=$(du -sm "$proj/.ruff_cache" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/.ruff_cache    ${sz}M"
        else
          rm -rf "$proj/.ruff_cache" && echo "  ✓ $rel/.ruff_cache removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # dist/ build/ (Python packages)
      for cache_dir in dist build; do
        if [[ -d "$proj/$cache_dir" ]]; then
          local sz
          sz=$(du -sm "$proj/$cache_dir" 2>/dev/null | cut -f1)
          if [[ $DRY_RUN -eq 1 ]]; then
            echo "  ⏭ $rel/$cache_dir      ${sz}M"
          else
            rm -rf "$proj/$cache_dir" && echo "  ✓ $rel/$cache_dir removed"
          fi
          (( total_items++ ))
          (( total_size += sz ))
        fi
      done
    done
    echo "  → Python cache/venv artifacts processed"

    # ── 4. PHP / Composer ──────────────────────────────────────────────────
    echo ""
    echo "[PHP/Composer]"

    local php_projects
    php_projects=$(find "$base_dir" -name 'composer.json' -type f -not -path '*/vendor/*' 2>/dev/null | xargs -I{} dirname {} 2>/dev/null | sort -u)

    for proj in $php_projects; do
      [[ -z "$proj" ]] && continue
      local rel="${proj#$base_dir/}"

      # vendor/
      if [[ -d "$proj/vendor" ]]; then
        local sz
        sz=$(du -sm "$proj/vendor" 2>/dev/null | cut -f1)
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/vendor         ${sz}M"
        else
          rm -rf "$proj/vendor" && echo "  ✓ $rel/vendor removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      fi

      # var/cache, var/log (Symfony/Laravel)
      find "$proj" -type d \( -name 'cache' -o -name 'log' \) -path '*/var/*' 2>/dev/null > "$tmpdir/php_caches"
      while read -r php_cache; do
        local sz
        sz=$(du -sm "$php_cache" 2>/dev/null | cut -f1)
        local rpath="${php_cache#$proj/}"
        if [[ $DRY_RUN -eq 1 ]]; then
          echo "  ⏭ $rel/$rpath  ${sz}M"
        else
          rm -rf "$php_cache" && echo "  ✓ $rel/$rpath removed"
        fi
        (( total_items++ ))
        (( total_size += sz ))
      done < "$tmpdir/php_caches"
    done
    echo "  → PHP vendor/cache artifacts processed"

    # ── 5. Go ──────────────────────────────────────────────────────────────
    echo ""
    echo "[Go]"

    # Global Go module cache (pkg/mod at project root)
    if [[ -d "$base_dir/pkg/mod" ]]; then
      local sz
      sz=$(du -sm "$base_dir/pkg/mod" 2>/dev/null | cut -f1)
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  ⏭ pkg/mod             ${sz}M (global Go module cache)"
      else
        rm -rf "$base_dir/pkg/mod" && echo "  ✓ pkg/mod (global Go cache) removed"
      fi
      (( total_items++ ))
      (( total_size += sz ))
    fi

    # Also clean global Go cache
    if command -v go &>/dev/null; then
      (go clean -cache 2>/dev/null) || true
      (go clean -testcache 2>/dev/null) || true
    fi
    echo "  → Go cache artifacts processed"

    # ── 6. IDE / misc caches ───────────────────────────────────────────────
    echo ""
    echo "[IDE / Misc]"

    # .idea/ (JetBrains — only real projects)
    find "$base_dir" -maxdepth 4 -name '.idea' -type d -not -path '*/node_modules/*' 2>/dev/null > "$tmpdir/ide_dirs"
    while read -r ide_dir; do
      local sz
      sz=$(du -sm "$ide_dir" 2>/dev/null | cut -f1)
      local rpath="${ide_dir#$base_dir/}"
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  ⏭ $rpath/.idea  ${sz}M"
      else
        rm -rf "$ide_dir" && echo "  ✓ $rpath/.idea removed"
      fi
      (( total_items++ ))
      (( total_size += sz ))
    done < "$tmpdir/ide_dirs"

    # .playwright-mcp/ (Playwright artifacts)
    find "$base_dir" -name '.playwright-mcp' -type d 2>/dev/null > "$tmpdir/playwright"
    while read -r pw_dir; do
      local sz
      sz=$(du -sm "$pw_dir" 2>/dev/null | cut -f1)
      local rpath="${pw_dir#$base_dir/}"
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  ⏭ $rpath  ${sz}M"
      else
        rm -rf "$pw_dir" && echo "  ✓ $rpath removed"
      fi
      (( total_items++ ))
      (( total_size += sz ))
    done < "$tmpdir/playwright"

    # tmp/ directories (project-level, skip deeply nested ones)
    find "$base_dir" -maxdepth 2 -name 'tmp' -type d 2>/dev/null > "$tmpdir/tmp_dirs"
    while read -r tmp_dir; do
      # Skip common false positives (Flutter plugin build tmp)
      case "$tmp_dir" in
        */charts/docs/tmp|*/scripts/tmp|*/app-flutter/build/*/tmp|*/app-flutter-release/build/*/tmp) continue ;;
      esac
      local sz
      sz=$(du -sm "$tmp_dir" 2>/dev/null | cut -f1)
      local rpath="${tmp_dir#$base_dir/}"
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  ⏭ $rpath  ${sz}M"
      else
        rm -rf "$tmp_dir" && echo "  ✓ $rpath removed"
      fi
      (( total_items++ ))
      (( total_size += sz ))
    done < "$tmpdir/tmp_dirs"

    # .temp/ directories
    find "$base_dir" -maxdepth 2 -name '.temp' -type d 2>/dev/null > "$tmpdir/temp_dirs"
    while read -r temp_dir; do
      local sz
      sz=$(du -sm "$temp_dir" 2>/dev/null | cut -f1)
      local rpath="${temp_dir#$base_dir/}"
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  ⏭ $rpath  ${sz}M"
      else
        rm -rf "$temp_dir" && echo "  ✓ $rpath removed"
      fi
      (( total_items++ ))
      (( total_size += sz ))
    done < "$tmpdir/temp_dirs"

    echo "  → IDE and misc artifacts processed"
  done

  # ── Summary ──────────────────────────────────────────────────────────────
  echo ""
  echo "╔══════════════════════════════════════════╗"
  echo "║  project_clean summary                   ║"
  echo "╠══════════════════════════════════════════╣"

  local size_str
  if (( total_size >= 1024 )); then
    size_str="$(( total_size / 1024 ))G"
  else
    size_str="${total_size}M"
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    printf "║  Would clean %6d dirs (~%-6s)           ║\n" "$total_items" "$size_str"
    printf "║  Run 'pclean --apply' to actually delete  ║\n"
  else
    printf "║  Cleaned   %6d dirs (~%-6s)           ║\n" "$total_items" "$size_str"
  fi
  echo "╚══════════════════════════════════════════╝"

  # Cleanup temp files
  rm -rf "$tmpdir"
}

show_help() {
  echo "Usage: pclean [OPTIONS]"
  echo ""
  echo "Finds projects by marker files (pubspec.yaml, package.json,"
  echo "pyproject.toml, composer.json, go.mod) and cleans their"
  echo "build/cache artifacts."
  echo ""
  echo "Modes:"
  echo "  (none / --dry-run)  Show what would be cleaned (default)"
  echo "  --apply             Actually delete files"
  echo "  --target DIR        Clean only this directory (use with --apply or --dry-run)"
  echo "  --help              Show this help"
  echo ""
  echo "Examples:"
  echo "  pclean                          # dry-run all projects"
  echo "  pclean --apply                  # actually delete all"
  echo "  pclean --target ~/work/KR       # dry-run work/KR only"
  echo "  pclean --target ~/work/KR --apply  # actually clean work/KR"
  echo ""
  echo "Cleans:"
  echo "  Flutter:  .dart_tool/, build/, .fvm/, android/.gradle,"
  echo "            android/.kotlin, .cxx, iOS/macOS Build/"
  echo "  Node.js:  node_modules/, .yarn/, .next/, .nuxt/"
  echo "  Python:   __pycache__, .venv/, .pytest_cache/, .ruff_cache/"
  echo "  PHP:      vendor/, var/cache/, var/log/"
  echo "  Go:       pkg/mod (global), vendor/"
  echo "  IDE:      .idea/"
  echo "  Misc:     .playwright-mcp/, tmp/, .temp/"
}
