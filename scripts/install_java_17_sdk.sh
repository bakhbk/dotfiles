#!/bin/bash

echo 'Checking if JAVA 17 SDK is installed'

if java -version 2>&1 | grep -q "17"; then
  echo 'JAVA 17 SDK is already installed'
else
  echo 'JAVA 17 SDK is not installed. Initiating installation...'
  echo 'Password may be required to install JAVA 17 SDK'
  brew reinstall --cask zulu@17
  echo "export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home" >>~/.zshrc
  echo "export PATH=\$JAVA_HOME/bin:\$PATH" >>~/.zshrc
  source ~/.zshrc
  echo 'JAVA 17 SDK installed successfully'
  echo 'Restart your IDE to apply changes'
fi
