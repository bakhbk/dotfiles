# Purpose:
# Set global environment variables for zsh.

# Set up locale (requred by some tools)
export LANG=ru_RU.UTF-8
export LC_CTYPE=ru_RU.UTF-8
export LC_ALL=ru_RU.UTF-8

# Github parameters
# export GITHUB_USER=

# Go stuff
export GOPATH=$HOME/work
export GOBIN=$GOPATH/bin

# generate function that returns nvim, vim or vi
function get_editor() {
    if command -v nvim &> /dev/null; then
        echo nvim
    elif command -v vim &> /dev/null; then
        echo vim
    else
        echo vi
    fi
}

# Preferred editor for local and remote sessions
export EDITOR=$(get_editor)
export GIT_EDITOR=$(get_editor)
export SVN_EDITOR=$(get_editor)

 # check is vscode if installed use code as VISUAL
if command -v code &> /dev/null; then
    export VISUAL=code
fi


if [[ "$OSTYPE" = darwin* ]]; then
    # X11 display for forwarding
    export DISPLAY=:0

    HOMEBREW_PREFIX=/usr/local
    if [[ $(/usr/bin/uname -m) == 'arm64' ]]; then
        HOMEBREW_PREFIX=/opt/homebrew
    fi

    # Force usage of OpenSSL from Homebrew.
    # You may also need to add -DOPENSSL_ROOT_DIR=$(brew --prefix)/opt/openssl to cmake
    # to properly find the library and headers.
    export LDFLAGS="-L$HOMEBREW_PREFIX/opt/openssl/lib"
    export CPPFLAGS="-I$HOMEBREW_PREFIX/opt/openssl/include"
    export CFLAGS="-I$(xcrun --show-sdk-path)/usr/include"
    export PKG_CONFIG_PATH="$HOMEBREW_PREFIX/opt/openssl/lib/pkgconfig"

    # Disables statistics that brew collects
    export HOMEBREW_NO_ANALYTICS=1
fi

if [[ "$OSTYPE" = linux* ]]; then
    export JAVA_HOME=$(readlink -f /usr/bin/java | sed "s:bin/java::")

    if [ -n "${SSH_CLIENT}" ]; then
        # Support ssh auth in docker builds when logged in from remote machine
        export SSH_AUTH_SOCK="${XDG_RUNTIME_DIR}/keyring/ssh"
    fi
fi

# Tell GPG which tty it should use
export GPG_TTY=$(tty)

# Suppress annoying 'use docker scan' suggestion
export DOCKER_SCAN_SUGGEST=false

# Show full log during docker build
export BUILDKIT_PROGRESS=plain

# Always store dependencies in local environments
export POETRY_VIRTUALENVS_IN_PROJECT=true

# For Android app developing purpose
export ANDROID_HOME=/Users/$USER/Library/Android/sdk
export JAVA_HOME=/Applications/Android\ Studio.app/Contents/jbr/Contents/Home
export PATH="$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator"

export PATH="/opt/homebrew/opt/ruby/bin:$PATH"
export PATH="$PATH":"$HOME/.pub-cache/bin"

# Load NVM
export NVM_DIR="$HOME/.nvm"
[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

# Set OrbStack as default Docker context
if command -v docker &> /dev/null && docker context ls -q | grep -q "orbstack"; then
    export DOCKER_CONTEXT=orbstack
fi
