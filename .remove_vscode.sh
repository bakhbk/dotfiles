#!/bin/zsh

echo "Removing Visual Studio Code..."

# Quit VS Code if running
osascript -e 'quit app "Visual Studio Code"'

# Remove main application
sudo rm -rf "/Applications/Visual Studio Code.app"

# Remove user settings, extensions, and cache
rm -rf "$HOME/Library/Application Support/Code"
rm -rf "$HOME/Library/Caches/com.microsoft.VSCode"
rm -rf "$HOME/Library/Caches/com.microsoft.VSCode.ShipIt"
rm -rf "$HOME/Library/Preferences/com.microsoft.VSCode.plist"
rm -rf "$HOME/Library/Saved Application State/com.microsoft.VSCode.savedState"
rm -rf "$HOME/.vscode"

# Remove command-line tool if installed
if [ -L "/usr/local/bin/code" ]; then
  sudo rm "/usr/local/bin/code"
fi

# Confirm removal
echo "VS Code and its related files have been removed."
