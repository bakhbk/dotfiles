#!/usr/bin/env bash

# Dotfiles uninstaller
# Safely removes dotfiles configuration and restores backups if available

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Show warning and get confirmation
confirm_uninstall() {
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                        WARNING!                              ║${NC}"
    echo -e "${RED}║                                                              ║${NC}"
    echo -e "${RED}║ This will remove all dotfiles configuration and may affect  ║${NC}"
    echo -e "${RED}║ your shell experience. Make sure you have backups!          ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    read -p "Are you sure you want to uninstall dotfiles? (type 'yes' to confirm): " -r
    if [[ $REPLY != "yes" ]]; then
        log_info "Uninstallation cancelled"
        exit 0
    fi
    
    read -p "Do you want to keep history backups? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        KEEP_HISTORY=true
    else
        KEEP_HISTORY=false
    fi
}

# Find and offer to restore backups
restore_backups() {
    log_info "Looking for backup directories..."
    
    local backup_dirs=(~/.dotfiles_backup_*)
    local latest_backup=""
    
    for backup_dir in "${backup_dirs[@]}"; do
        if [[ -d "$backup_dir" ]]; then
            latest_backup="$backup_dir"
        fi
    done
    
    if [[ -n "$latest_backup" ]]; then
        log_info "Found backup: $latest_backup"
        read -p "Do you want to restore from this backup? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Restoring from backup..."
            
            # Restore .zshrc if it exists in backup
            if [[ -f "$latest_backup/.zshrc" ]]; then
                cp "$latest_backup/.zshrc" ~/
                log_success "Restored ~/.zshrc"
            fi
            
            # Restore .tmux.conf if it exists in backup
            if [[ -f "$latest_backup/.tmux.conf" ]]; then
                cp "$latest_backup/.tmux.conf" ~/
                log_success "Restored ~/.tmux.conf"
            fi
            
            # Restore .dotfiles if it exists in backup
            if [[ -d "$latest_backup/dotfiles_old" ]]; then
                rm -rf ~/.dotfiles
                cp -r "$latest_backup/dotfiles_old" ~/.dotfiles
                log_success "Restored ~/.dotfiles"
            fi
            
            return 0
        fi
    else
        log_warning "No backup directories found"
    fi
    
    return 1
}

# Remove dotfiles configuration
remove_dotfiles() {
    log_info "Removing dotfiles configuration..."
    
    # Remove main config files from home directory
    local home_configs=(.zshrc .tmux.conf)
    for config in "${home_configs[@]}"; do
        if [[ -f ~/"$config" ]]; then
            log_info "Removing ~/$config"
            rm -f ~/"$config"
        fi
    done
    
    # Remove .dotfiles directory
    if [[ -d ~/.dotfiles ]]; then
        if [[ "$KEEP_HISTORY" == "true" && -d ~/.dotfiles/history_backups ]]; then
            log_info "Preserving history backups..."
            local temp_hist_backup="/tmp/dotfiles_history_backup_$(date +%Y%m%d_%H%M%S)"
            cp -r ~/.dotfiles/history_backups "$temp_hist_backup"
            rm -rf ~/.dotfiles
            mkdir -p ~/.dotfiles
            cp -r "$temp_hist_backup" ~/.dotfiles/history_backups
            rm -rf "$temp_hist_backup"
            log_success "History backups preserved in ~/.dotfiles/history_backups"
        else
            log_info "Removing ~/.dotfiles directory"
            rm -rf ~/.dotfiles
        fi
    fi
    
    # Remove Oh My Zsh if user wants to
    if [[ -d ~/.oh-my-zsh ]]; then
        read -p "Do you want to remove Oh My Zsh? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing Oh My Zsh..."
            rm -rf ~/.oh-my-zsh
            log_success "Oh My Zsh removed"
        fi
    fi
    
    # Remove fzf if user wants to
    if [[ -d ~/.fzf ]]; then
        read -p "Do you want to remove fzf? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing fzf..."
            rm -rf ~/.fzf
            # Remove fzf from shell configs
            sed -i.bak '/fzf/d' ~/.bashrc 2>/dev/null || true
            sed -i.bak '/fzf/d' ~/.zshrc 2>/dev/null || true
            log_success "fzf removed"
        fi
    fi
    
    log_success "Dotfiles configuration removed"
}

# Reset shell to system default
reset_shell() {
    if [[ "$SHELL" == *"zsh" ]]; then
        read -p "Do you want to change your default shell back to bash? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Changing default shell to bash..."
            chsh -s /bin/bash
            log_success "Default shell changed to bash"
            log_warning "You need to restart your terminal for this to take effect"
        fi
    fi
}

# Clean up backup directories
cleanup_backups() {
    read -p "Do you want to remove all backup directories? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing backup directories..."
        rm -rf ~/.dotfiles_backup_* ~/.dotfiles_update_backup_* 2>/dev/null || true
        log_success "Backup directories removed"
    else
        log_info "Backup directories preserved"
    fi
}

# Show post-uninstall message
show_post_uninstall() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  Uninstallation Complete                    ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║ Dotfiles have been removed from your system.                ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║ Next steps:                                                  ║${NC}"
    echo -e "${GREEN}║ 1. Restart your terminal to apply changes                   ║${NC}"
    echo -e "${GREEN}║ 2. Configure your shell manually if needed                  ║${NC}"
    
    if [[ "$KEEP_HISTORY" == "true" ]]; then
        echo -e "${GREEN}║ 3. Your history backups are preserved in ~/.dotfiles/       ║${NC}"
    fi
    
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
}

# Main uninstall function
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                   Dotfiles Uninstaller                      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Parse command line arguments
    local auto_confirm=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --yes|-y)
                auto_confirm=true
                KEEP_HISTORY=false
                shift
                ;;
            --keep-history)
                KEEP_HISTORY=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --yes, -y          Auto-confirm uninstallation"
                echo "  --keep-history     Keep history backups"
                echo "  --help, -h         Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Get confirmation if not auto-confirmed
    if [[ "$auto_confirm" != "true" ]]; then
        confirm_uninstall
    fi
    
    # Try to restore from backup first
    if ! restore_backups; then
        # If no backup restored, remove dotfiles
        remove_dotfiles
    fi
    
    # Reset shell if user wants
    reset_shell
    
    # Clean up backups if user wants
    cleanup_backups
    
    # Show completion message
    show_post_uninstall
    
    log_success "Dotfiles uninstallation completed!"
}

# Run main function with all arguments
main "$@"
