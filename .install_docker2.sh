#!/bin/bash

# Exit script on error and enable debugging
set -euxo pipefail

# Проверяем операционную систему
OS=$(uname -s)

if [ "$OS" == "Linux" ]; then
  echo "Updating package index..."
  sudo apt update && sudo apt upgrade -y

  echo "Installing required dependencies..."
  sudo apt install -y ca-certificates curl gnupg

  echo "Adding Docker's official GPG key..."
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  echo "Adding Docker repository..."
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  echo "Updating package index again..."
  sudo apt update

  echo "Installing Docker and Docker Compose..."
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  echo "Starting and enabling Docker service..."
  sudo systemctl enable --now docker

  echo "Adding current user to the Docker group (requires logout & login)..."
  sudo usermod -aG docker $USER

  echo "Docker and Docker Compose installation completed!"
  echo "To verify Docker, run: docker --version"
  echo "To verify Docker Compose, run: docker-compose --version"
  echo "You may need to log out and back in to use Docker without sudo."

elif [ "$OS" == "Darwin" ]; then
  echo "Checking if Homebrew is installed..."
  if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  echo "Installing Docker and Docker Compose on macOS..."
  brew install --cask docker
  brew install docker-compose

  echo "Please open Docker.app manually to complete the installation."
  echo "To verify Docker, run: docker --version"
  echo "To verify Docker Compose, run: docker-compose --version"
else
  echo "Unsupported operating system: $OS"
  exit 1
fi

# Проверяем, установлен ли Docker
if ! command -v docker &>/dev/null; then
  echo "Docker installation failed. Please check logs and install manually."
  exit 1
else
  echo "✅ docker installation completed!"
fi

# Проверяем, установлен ли Docker Compose
if ! command -v docker-compose &>/dev/null; then
  echo "Docker Compose installation failed. Please check logs and install manually."
  exit 1
else
  echo "✅ docker-compose installation completed!"
fi
