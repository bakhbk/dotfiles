#!/bin/bash

# Define the DMG URL - This ensures the latest version for an Intel or Apple Silicon Mac.
CHROME_DMG_URL="https://dl.google.com/chrome/mac/stable/GGRO/googlechrome.dmg"
DMG_FILE="googlechrome.dmg"
MOUNT_POINT="/Volumes/Google Chrome"
APP_NAME="Google Chrome.app"
APPLICATIONS_DIR="/Applications"

echo "------------------------------------------"
echo "Starting total uninstallation and reinstallation of Google Chrome on macOS..."
echo "------------------------------------------"

# --- Step 1: Uninstall Google Chrome ---

echo "1. Quitting Google Chrome..."
# Attempt to quit the application gracefully
killall "Google Chrome" &> /dev/null

# Force quit if it's still running after a moment
sleep 2
pkill -9 "Google Chrome" &> /dev/null

echo "2. Deleting Google Chrome application..."
# Remove the application bundle
sudo rm -rf "$APPLICATIONS_DIR/$APP_NAME"

echo "3. Deleting all user profile information (bookmarks, history, cache, etc.)..."
# Remove associated directories in the user Library
rm -rf ~/Library/Application\ Support/Google/Chrome/
rm -rf ~/Library/Caches/Google/Chrome/
rm -rf ~/Library/Preferences/com.google.Chrome.plist
rm -rf ~/Library/Saved\ Application\ State/com.google.Chrome.savedState/

echo "4. Emptying the Trash for permanent removal..."
# Empty trash can silently for the current user
eval `printf "osascript -e 'tell app \"Finder\" to empty trash'"`

echo "------------------------------------------"
echo "Google Chrome and all data have been completely removed."
echo "------------------------------------------"

# --- Step 2: Install Google Chrome ---

echo "5. Downloading the latest Google Chrome installer..."
# Navigate to the Downloads directory (or a temp directory) and download the DMG file
cd ~/Downloads
curl -O $CHROME_DMG_URL

echo "6. Mounting the installer disk image..."
# Mount the DMG file silently
hdiutil attach $DMG_FILE -nobrowse -quiet -mountpoint "$MOUNT_POINT"

echo "7. Installing Google Chrome to the Applications folder (may ask for password)..."
# Copy the application to the Applications folder
# Use sudo cp to ensure all permissions are handled correctly and it goes to the main Applications folder
sudo cp -R "$MOUNT_POINT/$APP_NAME" "$APPLICATIONS_DIR"

echo "8. Unmounting the disk image..."
# Unmount the DMG
hdiutil detach "$MOUNT_POINT" -quiet

echo "9. Deleting the downloaded .dmg file..."
# Remove the installer file
rm $DMG_FILE

echo "------------------------------------------"
echo "Google Chrome reinstallation is complete."
echo "You can now find it in your Applications folder."
echo "------------------------------------------"

# --- Step 3: Launch the new Chrome instance (Optional) ---
# echo "10. Launching the newly installed Google Chrome..."
# open -a "Google Chrome"
