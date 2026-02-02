#!/bin/zsh

cci() {
  (
    if ! command -v "$1" &>/dev/null; then
      echo "Installing $1..."
      eval "$2"
      echo "✅ $1 installed"
    else
      echo "✓ $1 is already installed"
    fi
  )
}

ccv() {
  (
    if eval "$2" &>/dev/null; then
      echo "→ $1 $(eval "$2")"
    else
      echo "❌ $1 not found or an error occurred"
    fi
  )
}

add_to_zshrc() {
  local line="$1"
  if ! grep -q "$line" ~/.zshrc 2>/dev/null; then
    echo "$line" >> ~/.zshrc
    echo "✅ Added to ~/.zshrc: $line"
  else
    echo "✓ Already in ~/.zshrc: $line"
  fi
}

echo "Starting project setup..."
# Installing Homebrew
cci "brew" "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""

# Installing fvm
cci "fvm" "curl -fsSL https://fvm.app/install.sh | bash"

# Installing protoc
cci "protoc" "brew install protobuf"

# Installing Task
cci "task" "brew install go-task"

# Installing grpcui for generating gRPC service documentation
cci "grpcui" "brew install grpcui"

# Installing mjml (for email templates)
cci "mjml" "brew install mjml"

# Installing git flow for branch management
cci "git flow" "brew install git-flow-avh"

# Installing grpcurl for testing gRPC services
cci "grpcurl" "brew install grpcurl"

# Checking Flutter installation via fvm
for dir in $(ls -d */); do
  (
	if [ -f "$dir/.fvmrc" ]; then
		echo "Checking Flutter in $dir..."
		cd "$dir" || exit
		fvm use --force -s 3.38.3
		fvm dart --disable-analytics
		fvm flutter --disable-analytics
		cd - || exit
		echo "✅ Flutter checked in $dir"
	else
		echo "⚠️ File $dir/.fvmrc not found, skipping..."
	fi
  )
done

# Adding fvm flutter to PATH for current session
export PATH="$HOME/.fvm/default/bin:$PATH"

# Installing protoc-gen-dart globally
echo "Installing protoc-gen-dart..."
fvm dart pub global activate protoc_plugin 22.5.0
echo "✅ protoc-gen-dart installed"

# Adding dart pub global bin to PATH
export PATH="$HOME/.pub-cache/bin:$PATH"

# Checking installation
echo "Versions of installed tools:"
ccv "brew version:" "brew --version"
ccv "protoc version:" "protoc --version"
ccv "task version:" "task --version"
ccv "grpcurl version:" "grpcurl --version"
ccv "fvm version:" "fvm --version"
ccv "flutter version:" "fvm flutter --version | head -1"
ccv "dart version:" "fvm dart --version"
ccv "grpcui version:" "grpcui --version"
ccv "mjml version:" "mjml --version"

# Checking protoc-gen-dart
if command -v protoc-gen-dart &>/dev/null; then
  echo "✓ protoc-gen-dart is available in PATH"
else
  echo "❌ protoc-gen-dart not found in PATH"
  add_to_zshrc 'export PATH="$HOME/.pub-cache/bin:$PATH"'
  add_to_zshrc 'export PATH="$HOME/.fvm/default/bin:$PATH"'
  echo ""
  echo "Restart the terminal or run:"
  echo "source ~/.zshrc"
fi

echo ""
echo "✅ Setup completed!"
echo ""