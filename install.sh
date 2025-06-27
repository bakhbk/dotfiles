#!/usr/bin/env bash

# Enhanced dotfiles installer
# Install common configuration files to the local or remote machine.
# Regarding usage see the README.md.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Configuration files to be installed in ~/.dotfiles/
CONFIGS=(
  .zsh_aliases
  .zsh_tools
  .zsh_history_config
  .zshenv
  .zshrc
  .install-oh-my-zsh.sh
  .shell_prompt
  .git_checkout_branch.sh
  .git_delete_branch.sh
  .tmux_session_selector.sh
  .nvmv.sh
  .minimal.zshrc
  .create_tmux_session.sh
  .install_fzf.sh
  .install-zsh.sh
  .install_docker.sh
  .install_tmuxp.sh
  .clean_docker.sh
  .reset_vpn.sh
)

# Configuration files to be copied to home directory
CONFIGS_HOME_DIR=(
  .tmux.conf
  .zshrc
)

# Optional tools to install
OPTIONAL_TOOLS=(
  "oh-my-zsh:./.install-oh-my-zsh.sh"
  "fzf:./.install_fzf.sh"
  "zsh:./.install-zsh.sh"
  "docker:./.install_docker.sh"
  "tmuxp:./.install_tmuxp.sh"
)

# Check if running on macOS
is_macos() {
    [[ "$OSTYPE" == "darwin"* ]]
}

# Check if running on Linux
is_linux() {
    [[ "$OSTYPE" == "linux-gnu"* ]]
}

# Create backup of existing files
backup_existing() {
    local backup_dir=~/.dotfiles_backup_$(date +%Y%m%d_%H%M%S)
    
    log_info "Creating backup directory: $backup_dir"
    mkdir -p "$backup_dir"
    
    # Backup existing dotfiles
    for config in "${CONFIGS_HOME_DIR[@]}"; do
        if [[ -f ~/"$config" ]]; then
            log_info "Backing up existing ~/$config"
            cp ~/"$config" "$backup_dir/"
        fi
    done
    
    # Backup existing ~/.dotfiles if it exists
    if [[ -d ~/.dotfiles ]]; then
        log_info "Backing up existing ~/.dotfiles"
        cp -r ~/.dotfiles "$backup_dir/dotfiles_old"
    fi
    
    log_success "Backup created in $backup_dir"
}

# Install configuration files
install_configs() {
    log_step "Installing configuration files..."
    
    # Create ~/.dotfiles directory
    mkdir -p ~/.dotfiles
    mkdir -p ~/.dotfiles/history_backups
    
    # Copy configs to ~/.dotfiles/
    for config in "${CONFIGS[@]}"; do
        if [[ -f "$config" ]]; then
            log_info "Installing $config to ~/.dotfiles/"
            cp -f "$config" ~/.dotfiles/
        else
            log_warning "Config file not found: $config"
        fi
    done
    
    # Copy configs to home directory
    for config in "${CONFIGS_HOME_DIR[@]}"; do
        if [[ -f "$config" ]]; then
            log_info "Installing $config to home directory"
            cp -f "$config" ~/
        else
            log_warning "Config file not found: $config"
        fi
    done
    
    # Copy scripts directory
    if [[ -d "scripts" ]]; then
        log_info "Installing scripts directory"
        cp -r scripts ~/.dotfiles/
        chmod +x ~/.dotfiles/scripts/*.sh
    fi
    
    # Copy git configuration
    if [[ -d "git" ]]; then
        log_info "Installing git configuration"
        cp -r git ~/.dotfiles/
    fi
    
    log_success "Configuration files installed successfully"
}

# Check system dependencies
check_dependencies() {
    log_step "Checking system dependencies..."
    
    local missing_deps=()
    
    # Check for git
    if ! command -v git >/dev/null; then
        missing_deps+=("git")
    fi
    
    # Check for curl
    if ! command -v curl >/dev/null; then
        missing_deps+=("curl")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install missing dependencies and run again"
        
        if is_macos; then
            log_info "On macOS, you can install with: brew install ${missing_deps[*]}"
        elif is_linux; then
            log_info "On Ubuntu/Debian: sudo apt update && sudo apt install ${missing_deps[*]}"
            log_info "On CentOS/RHEL: sudo yum install ${missing_deps[*]}"
        fi
        exit 1
    fi
    
    log_success "All dependencies are available"
}

# Install optional tools
install_optional_tools() {
    log_step "Installing optional tools..."
    
    for tool_entry in "${OPTIONAL_TOOLS[@]}"; do
        IFS=':' read -r tool_name script_path <<< "$tool_entry"
        
        if [[ -f "$script_path" ]]; then
            read -p "Do you want to install $tool_name? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Installing $tool_name..."
                chmod +x "$script_path"
                if "$script_path"; then
                    log_success "$tool_name installed successfully"
                else
                    log_error "Failed to install $tool_name"
                fi
            else
                log_info "Skipping $tool_name installation"
            fi
        else
            log_warning "Installation script not found for $tool_name: $script_path"
        fi
    done
}

# Set up shell configuration
setup_shell() {
    log_step "Setting up shell configuration..."
    
    # Make zsh the default shell if it's available and not already default
    if command -v zsh >/dev/null; then
        if [[ "$SHELL" != *"zsh" ]]; then
            read -p "Do you want to set zsh as your default shell? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Setting zsh as default shell..."
                if is_macos; then
                    chsh -s /bin/zsh
                else
                    chsh -s "$(which zsh)"
                fi
                log_success "Default shell set to zsh"
            fi
        else
            log_info "zsh is already the default shell"
        fi
    else
        log_warning "zsh is not installed. Consider installing it for the best experience."
    fi
}

# Show post-installation instructions
show_post_install() {
    log_step "Post-installation setup"
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    Installation Complete!                    ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║ Next steps:                                                  ║${NC}"
    echo -e "${CYAN}║ 1. Restart your terminal or run: source ~/.zshrc            ║${NC}"
    echo -e "${CYAN}║ 2. Run history maintenance: ~/.dotfiles/scripts/history_... ║${NC}"
    echo -e "${CYAN}║ 3. Configure git if needed: git config --global user.name   ║${NC}"
    echo -e "${CYAN}║ 4. Test new features: fh, hs, history_stats                 ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    
    echo ""
    log_info "Available new commands:"
    echo "  • fh - fuzzy history search"
    echo "  • hs - history statistics"
    echo "  • sl - sudo last command"
    echo "  • efh - execute from history"
    echo "  • ~/.dotfiles/scripts/history_maintenance.sh - history management"
}

# Main installation function
main() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                     Dotfiles Installer                      ║${NC}"
    echo -e "${CYAN}║                Enhanced with history features               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-backup)
                NO_BACKUP=true
                shift
                ;;
            --no-optional)
                NO_OPTIONAL=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --no-backup    Skip creating backup of existing files"
                echo "  --no-optional  Skip installing optional tools"
                echo "  --help, -h     Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check dependencies
    check_dependencies
    
    # Create backup unless disabled
    if [[ "${NO_BACKUP:-false}" != "true" ]]; then
        backup_existing
    fi
    
    # Install configuration files
    install_configs
    
    # Install optional tools unless disabled
    if [[ "${NO_OPTIONAL:-false}" != "true" ]]; then
        install_optional_tools
    fi
    
    # Set up shell
    setup_shell
    
    # Show post-installation instructions
    show_post_install
    
    log_success "Dotfiles installation completed successfully!"
}

# Run main function with all arguments
main "$@"
