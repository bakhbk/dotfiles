#!/usr/bin/env bash
# MCP servers setup (config lives in ./mcp.json).
# Usage: setup.sh [install|reinstall|uninstall]   (default: install)
# Test:  bash -n setup.sh
set -euo pipefail

NPM=(
    "@modelcontextprotocol/server-filesystem"
    "@modelcontextprotocol/server-sequential-thinking"
    "@playwright/mcp"
    "@upstash/context7-mcp"
    "mcp-duckduckgo"
    "g-search-mcp"
    "@beledarian/mcp-local-memory"
    "@gethopp/figma-mcp-bridge"
)
UVX=(duckduckgo-mcp-server mcp-server-fetch arxiv-mcp-server markitdown-mcp)
# mcp 2.x broke these servers (old SDK API), so the SDK is pinned to mcp<2.
PINNED=(mcp-server-sqlite paper-search-mcp droidmind)

MODE=${1:-install}; MODE=${MODE#--}   # accepts "reinstall" and "--reinstall"

ok()   { printf '\033[0;32m✓ %s\033[0m\n' "$1"; }
warn() { printf '\033[0;33m⚠ %s\033[0m\n' "$1"; }
step() { printf '\n\033[0;36m▶ %s\033[0m\n' "$1"; }

# Sequential: npm and uv share one global store, concurrent installs race.
npm_op() {
    if [[ $MODE == uninstall ]]; then
        npm uninstall -g "$1" --silent 2>/dev/null && ok "$1 removed" || warn "$1 not installed"
    else
        [[ $MODE == reinstall ]] && npm uninstall -g "$1" --silent 2>/dev/null || true
        npm install -g "$1" --no-audit --silent && ok "$1" || warn "$1"
    fi
}
uv_op() {
    if [[ $MODE == uninstall ]]; then
        uv tool uninstall "$1" --quiet 2>/dev/null && ok "$1 removed" || warn "$1 not installed"
    else
        uv tool install "$1" --force --quiet && ok "$1" || warn "$1"
    fi
}

step "Dependencies"
for c in node npm uv; do
    command -v "$c" >/dev/null || { warn "$c is required"; exit 1; }
done

if [[ $MODE == uninstall ]]; then
    step "Removing packages"
    for p in "${NPM[@]}"; do npm_op "$p"; done
    for p in "${UVX[@]}"; do uv_op "$p"; done
    for p in "${PINNED[@]}"; do uv tool uninstall "$p" --quiet 2>/dev/null && ok "$p removed" || warn "$p not installed"; done
    if command -v go >/dev/null; then
        rm -f "$(go env GOPATH)/bin/gopls" "$(go env GOPATH)/bin/mcp-gopls"
        ok "go binaries removed"
    fi
    ok "uninstall done"
    exit 0
fi

step "Installing ${#NPM[@]} npm + ${#UVX[@]} uvx servers"
for p in "${NPM[@]}"; do npm_op "$p"; done
for p in "${UVX[@]}"; do uv_op "$p"; done

step "uvx servers needing a pinned mcp SDK"
uv tool install --with 'mcp<2' mcp-server-sqlite --force --quiet 2>/dev/null && ok "mcp-server-sqlite" || warn "mcp-server-sqlite"
uv tool install --with 'mcp<2' paper-search-mcp --force --quiet 2>/dev/null && ok "paper-search-mcp" || warn "paper-search-mcp"
uv tool install --python 3.13 --with 'mcp<2' --from git+https://github.com/hyperb1iss/droidmind droidmind --quiet 2>/dev/null && ok "droidmind" || warn "droidmind"

step "Playwright Chromium (browser for @playwright/mcp)"
npx -y playwright install chromium && ok "chromium" || warn "chromium install failed"

step "Go (optional): gopls MCP (built into gopls)"
if command -v go >/dev/null; then
    go install golang.org/x/tools/gopls@latest && ok "gopls" || warn "gopls"
else
    warn "go not found — skipping"
fi

step "Dart (optional): built-in dart mcp-server"
if command -v dart >/dev/null; then
    ok "dart $(dart --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
else
    warn "dart not found"
fi

ok "setup done"
