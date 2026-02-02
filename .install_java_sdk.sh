#!/bin/zsh

JDK_VERSION=${1:-17}

JDK_PATH="/Library/Java/JavaVirtualMachines/zulu-$JDK_VERSION.jdk/Contents/Home"

echo "Checking if JAVA $JDK_VERSION SDK is installed"
if [ ! -d "$JDK_PATH" ]; then
    echo "JAVA $JDK_VERSION SDK is not installed. Initiating installation..."
    echo 'Password may be required to install JAVA $JDK_VERSION SDK'
    brew reinstall --cask zulu@$JDK_VERSION
else
    echo "JAVA $JDK_VERSION SDK is already installed."
fi

if ! grep -q "export JAVA_HOME=$JDK_PATH" ~/.zshrc; then
    echo "export JAVA_HOME=$JDK_PATH" >> ~/.zshrc
fi
if ! grep -q "export PATH=\$JAVA_HOME/bin:\$PATH" ~/.zshrc; then
    echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> ~/.zshrc
fi

if ! fvm flutter doctor -v 2>/dev/null | grep -q "Java binary at: $JDK_PATH/bin/java"; then
    echo "Configuring Flutter to use JDK at $JDK_PATH"
    fvm flutter config --jdk-dir="$JDK_PATH"
fi


echo "⚠️ If you are using an Android Studio change the JDK path in Preferences > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK to Zulu $JDK_VERSION"

echo "✅ JAVA $JDK_VERSION SDK installed successfully"

echo 'ℹ️ Restart your IDE to apply changes'