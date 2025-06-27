#!/bin/bash

function _nvmv() {
  local version="$1"
  local arch="$2"

  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"                   # This loads nvm
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" # This loads nvm bash_completion

  if ! command -v nvm 2>&1 >/dev/null; then
    echo "nvm not found. Installing..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"                   # This loads nvm
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" # This loads nvm bash_completion
  fi

  if [[ "$1" == "-h" ]]; then
    echo "Usage: nvmv <version> [architecture]"
    echo "  <version>: The Node.js version to install and use (e.g., v16, v18, latest)."
    echo "  [architecture]: The architecture to install (e.g., x86_64, arm64). Optional."
    echo "Example: nvmv v20 x86_64"
    echo "Example: nvmv latest"
    return 0
  fi

  if [[ -z "$version" ]]; then
    echo "Error: Please provide a Node.js version."
    nvmv -h
    return 1
  fi

  if [[ -z "$arch" ]]; then
    arch=$(uname -m) # Default to current architecture
  fi

  nvm install "$version" "$arch"
  if [[ $? -ne 0 ]]; then # Check if nvm install failed
    echo "Error: Failed to install Node.js version $version for architecture $arch"
    return 1
  fi

  nvm use "$version"
  if [[ $? -ne 0 ]]; then # Check if nvm use failed
    echo "Error: Failed to switch to Node.js version $version"
    return 1
  fi

  # Check if npm or yarn is not found
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm or yarn not found. Setting default alias to node..."
    nvm alias default node
  fi

  echo "Current npm version: $(npm --version)"
  echo "Now can run required commands"
  echo "npm install --lts"
  echo "npm install yarn"
  echo "npx yarn install --ignore-engines"
}

alias nvmv='_nvmv'
