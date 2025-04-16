#!/bin/zsh

echo 'Checking if JAVA 11 SDK is installed'

# Check if Java 11 is already installed at the specified path
if [[ -d "/Library/Java/JavaVirtualMachines/zulu-11.jdk/Contents/Home" ]]; then
    echo 'JAVA 11 SDK is already installed at /Library/Java/JavaVirtualMachines/zulu-11.jdk/Contents/Home'
else
    # If not installed, install Java 11 using Homebrew
    echo 'JAVA 11 SDK is not installed. Initiating installation...'
    echo 'Password may be required to install JAVA 11 SDK'
    brew reinstall --cask zulu@11 || { echo 'Failed to install JAVA 11 SDK'; exit 1; }
    echo 'JAVA 11 SDK installed successfully'
fi

# Export JAVA_HOME and PATH to .zshrc if they are not already present
if ! grep -q "export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-11.jdk/Contents/Home" ~/.zshrc; then
    echo "export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-11.jdk/Contents/Home" >> ~/.zshrc
    echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> ~/.zshrc
    echo 'JAVA_HOME and PATH have been added to your .zshrc file'
else
    echo 'JAVA_HOME and PATH are already configured in your .zshrc file'
fi

# Reload the .zshrc file to apply changes
source ~/.zshrc

# Verify that Java 11 is now active
if java -version 2>&1 | grep -q "11"; then
    echo 'JAVA 11 SDK is now active'
    echo 'Restart your IDE to apply changes if necessary'
else
    echo 'Failed to activate JAVA 11 SDK. Please check your installation and configuration.'
fi
