#!/usr/bin/env bash

# Dotfiles updater script
# Updates existing dotfiles installation with latest changes

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Check if this is a git repository
check_git_repo() {
    if [[ ! -d .git ]]; then
        log_error "This is not a git repository. Cannot update."
        log_info "If you want to enable updates, initialize git:"
        log_info "  git init"
        log_info "  git remote add origin <your-repo-url>"
        exit 1
    fi
}

# Pull latest changes
update_from_git() {
    log_step "Updating from git repository..."
    
    # Check if we have a remote
    if ! git remote >/dev/null 2>&1; then
        log_warning "No git remote configured. Skipping git update."
        return 0
    fi
    
    # Stash any local changes
    if ! git diff --quiet; then
        log_info "Stashing local changes..."
        git stash push -m "Auto-stash before update $(date)"
    fi
    
    # Pull latest changes
    log_info "Pulling latest changes..."
    if git pull; then
        log_success "Successfully updated from git"
    else
        log_error "Failed to update from git"
        return 1
    fi
}

# Update configuration files
update_configs() {
    log_step "Updating configuration files..."
    
    # Create backup
    local backup_dir=~/.dotfiles_update_backup_$(date +%Y%m%d_%H%M%S)
    mkdir -p "$backup_dir"
    
    # Backup current configs
    if [[ -d ~/.dotfiles ]]; then
        cp -r ~/.dotfiles "$backup_dir/dotfiles_old"
        log_info "Backup created: $backup_dir"
    fi
    
    # Run the installer in update mode
    if [[ -f install.sh ]]; then
        log_info "Running installer to update configs..."
        ./install.sh --no-optional
    else
        log_error "install.sh not found. Cannot update configs."
        return 1
    fi
}

# Update Oh My Zsh if installed
update_oh_my_zsh() {
    if [[ -d ~/.oh-my-zsh ]]; then
        log_step "Updating Oh My Zsh..."
        
        cd ~/.oh-my-zsh
        if git pull; then
            log_success "Oh My Zsh updated"
        else
            log_warning "Failed to update Oh My Zsh"
        fi
        cd - >/dev/null
        
        # Update plugins
        local plugins_dir=~/.oh-my-zsh/custom/plugins
        
        for plugin_dir in "$plugins_dir"/*; do
            if [[ -d "$plugin_dir/.git" ]]; then
                plugin_name=$(basename "$plugin_dir")
                log_info "Updating plugin: $plugin_name"
                cd "$plugin_dir"
                git pull || log_warning "Failed to update $plugin_name"
                cd - >/dev/null
            fi
        done
    else
        log_info "Oh My Zsh not installed, skipping update"
    fi
}

# Update fzf if installed
update_fzf() {
    if [[ -d ~/.fzf ]]; then
        log_step "Updating fzf..."
        
        cd ~/.fzf
        if git pull; then
            log_success "fzf updated"
            log_info "Re-running fzf install..."
            ./install --key-bindings --completion --update-rc
        else
            log_warning "Failed to update fzf"
        fi
        cd - >/dev/null
    else
        log_info "fzf not installed, skipping update"
    fi
}

# Clean up old files
cleanup_old_files() {
    log_step "Cleaning up old files..."
    
    # Remove old backup files (keep last 5)
    local backup_dirs=(~/.dotfiles_backup_* ~/.dotfiles_update_backup_*)
    if [[ ${#backup_dirs[@]} -gt 5 ]]; then
        log_info "Removing old backup directories..."
        ls -dt ~/.dotfiles_backup_* ~/.dotfiles_update_backup_* 2>/dev/null | tail -n +6 | xargs rm -rf
    fi
    
    # Clean up history backups (keep last 10)
    if [[ -d ~/.dotfiles/history_backups ]]; then
        local hist_backups=(~/.dotfiles/history_backups/*)
        if [[ ${#hist_backups[@]} -gt 10 ]]; then
            log_info "Cleaning old history backups..."
            ls -dt ~/.dotfiles/history_backups/* 2>/dev/null | tail -n +11 | xargs rm -f
        fi
    fi
    
    log_success "Cleanup completed"
}

# Verify update
verify_update() {
    log_step "Verifying update..."
    
    if [[ -f scripts/verify_installation.sh ]]; then
        chmod +x scripts/verify_installation.sh
        if ./scripts/verify_installation.sh; then
            log_success "Update verification passed"
            return 0
        else
            log_warning "Update verification found issues"
            return 1
        fi
    else
        log_warning "Verification script not found, skipping verification"
        return 0
    fi
}

# Show update summary
show_summary() {
    log_step "Update Summary"
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Update Complete!                         ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║ Your dotfiles have been updated successfully.               ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║ Next steps:                                                  ║${NC}"
    echo -e "${GREEN}║ 1. Restart your terminal or run: source ~/.zshrc            ║${NC}"
    echo -e "${GREEN}║ 2. Test new features and configurations                     ║${NC}"
    echo -e "${GREEN}║ 3. Report any issues on the project repository              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
}

# Main update function
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                     Dotfiles Updater                        ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Parse command line arguments
    local skip_git=false
    local skip_verification=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-git)
                skip_git=true
                shift
                ;;
            --skip-verification)
                skip_verification=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --skip-git         Skip git update"
                echo "  --skip-verification Skip update verification"
                echo "  --help, -h         Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run update steps
    if [[ "$skip_git" != "true" ]]; then
        check_git_repo
        update_from_git || exit 1
    fi
    
    update_configs || exit 1
    update_oh_my_zsh
    update_fzf
    cleanup_old_files
    
    if [[ "$skip_verification" != "true" ]]; then
        verify_update
    fi
    
    show_summary
    log_success "Dotfiles update completed successfully!"
}

# Run main function with all arguments
main "$@"
