#!/bin/bash

set -euxo pipefail

# Check if a username is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <username>"
  exit 1
fi

USERNAME=$1

# Create the user
sudo adduser --gecos "" $USERNAME

# Set a password (you can modify this part to auto-generate)
echo "Set a password for $USERNAME:"
sudo passwd $USERNAME

# Optional: Add user to the sudo group
read -p "Grant sudo privileges to $USERNAME? (y/n): " SUDO_ANSWER
if [[ "$SUDO_ANSWER" == "y" ]]; then
  sudo usermod -aG sudo $USERNAME
  sudo usermod -aG $USERNAME www-data
  echo "$USERNAME has been added to the sudo group."
fi

echo "User $USERNAME created successfully!"
