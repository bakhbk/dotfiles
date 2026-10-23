#!/usr/bin/env bash
# Symlink scripts/converters/md_to_pdf.py to ~/.local/bin/md2pdf
set -eu

BIN_DIR="${HOME}/.local/bin"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/converters/md_to_pdf.py"

mkdir -p "$BIN_DIR"
chmod +x "$SRC"
ln -sf "$SRC" "$BIN_DIR/md2pdf"
echo "md2pdf -> $BIN_DIR/md2pdf"
