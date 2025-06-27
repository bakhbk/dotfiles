#!/usr/bin/env bash

# Dotfiles installation verification script
# This script checks if all dotfiles components are properly installed

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
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if file exists and report
check_file() {
    local file_path="$1"
    local description="$2"
    
    if [[ -f "$file_path" ]]; then
        log_success "$description exists: $file_path"
        return 0
    else
        log_error "$description missing: $file_path"
        return 1
    fi
}

# Check if directory exists and report
check_directory() {
    local dir_path="$1"
    local description="$2"
    
    if [[ -d "$dir_path" ]]; then
        log_success "$description exists: $dir_path"
        return 0
    else
        log_error "$description missing: $dir_path"
        return 1
    fi
}

# Check if command exists
check_command() {
    local command="$1"
    local description="$2"
    
    if command -v "$command" >/dev/null 2>&1; then
        log_success "$description is available: $(which "$command")"
        return 0
    else
        log_warning "$description not found: $command"
        return 1
    fi
}

# Check zsh configuration
check_zsh_config() {
    log_info "Checking zsh configuration..."
    
    local issues=0
    
    # Check main config files
    check_file ~/.zshrc "Main zsh config" || ((issues++))
    check_file ~/.dotfiles/.zshrc "Dotfiles zsh config" || ((issues++))
    check_file ~/.dotfiles/.zsh_aliases "Zsh aliases" || ((issues++))
    check_file ~/.dotfiles/.zsh_tools "Zsh tools" || ((issues++))
    check_file ~/.dotfiles/.zsh_history_config "History config" || ((issues++))
    check_file ~/.dotfiles/.zshenv "Zsh environment" || ((issues++))
    check_file ~/.dotfiles/.shell_prompt "Shell prompt" || ((issues++))
    
    # Check history file
    if [[ -f ~/.dotfiles/.zsh_history ]]; then
        local hist_size=$(wc -l < ~/.dotfiles/.zsh_history 2>/dev/null || echo 0)
        log_success "History file exists with $hist_size entries"
    else
        log_warning "History file not found (will be created on first use)"
    fi
    
    return $issues
}

# Check tmux configuration
check_tmux_config() {
    log_info "Checking tmux configuration..."
    
    local issues=0
    
    check_file ~/.tmux.conf "Tmux config" || ((issues++))
    check_file ~/.dotfiles/.create_tmux_session.sh "Tmux session creator" || ((issues++))
    check_file ~/.dotfiles/.tmux_session_selector.sh "Tmux session selector" || ((issues++))
    
    return $issues
}

# Check git configuration
check_git_config() {
    log_info "Checking git configuration..."
    
    local issues=0
    
    check_file ~/.dotfiles/.git_checkout_branch.sh "Git checkout script" || ((issues++))
    check_file ~/.dotfiles/.git_delete_branch.sh "Git delete branch script" || ((issues++))
    
    if [[ -d ~/.dotfiles/git ]]; then
        log_success "Git configuration directory exists"
    else
        log_warning "Git configuration directory not found"
        ((issues++))
    fi
    
    return $issues
}

# Check scripts
check_scripts() {
    log_info "Checking scripts..."
    
    local issues=0
    
    check_directory ~/.dotfiles/scripts "Scripts directory" || ((issues++))
    check_file ~/.dotfiles/scripts/history_maintenance.sh "History maintenance script" || ((issues++))
    
    # Check if scripts are executable
    if [[ -f ~/.dotfiles/scripts/history_maintenance.sh ]]; then
        if [[ -x ~/.dotfiles/scripts/history_maintenance.sh ]]; then
            log_success "History maintenance script is executable"
        else
            log_warning "History maintenance script is not executable"
            ((issues++))
        fi
    fi
    
    return $issues
}

# Check optional tools
check_optional_tools() {
    log_info "Checking optional tools..."
    
    # These are optional, so we don't count them as issues
    check_command "zsh" "Zsh shell"
    check_command "tmux" "Tmux"
    check_command "git" "Git"
    check_command "fzf" "Fzf fuzzy finder"
    check_command "curl" "Curl"
    
    # Check Oh My Zsh
    if [[ -d ~/.oh-my-zsh ]]; then
        log_success "Oh My Zsh is installed"
        
        # Check Oh My Zsh plugins
        local plugins_dir=~/.oh-my-zsh/custom/plugins
        [[ -d "$plugins_dir/zsh-autosuggestions" ]] && log_success "zsh-autosuggestions plugin installed"
        [[ -d "$plugins_dir/you-should-use" ]] && log_success "you-should-use plugin installed"
        [[ -d "$plugins_dir/zsh-syntax-highlighting" ]] && log_success "zsh-syntax-highlighting plugin installed"
    else
        log_info "Oh My Zsh not installed (optional)"
    fi
}

# Check environment variables and settings
check_environment() {
    log_info "Checking environment settings..."
    
    # Check if zsh is the default shell
    if [[ "$SHELL" == *"zsh" ]]; then
        log_success "Zsh is the default shell"
    else
        log_warning "Zsh is not the default shell (current: $SHELL)"
    fi
    
    # Check important environment variables in a new zsh instance
    if command -v zsh >/dev/null; then
        local histfile=$(zsh -c 'echo $HISTFILE' 2>/dev/null || echo "")
        local histsize=$(zsh -c 'echo $HISTSIZE' 2>/dev/null || echo "")
        
        if [[ -n "$histfile" ]]; then
            log_success "HISTFILE is set: $histfile"
        else
            log_warning "HISTFILE not set"
        fi
        
        if [[ "$histsize" == "100000" ]]; then
            log_success "HISTSIZE is properly set: $histsize"
        else
            log_warning "HISTSIZE not set to 100000 (current: $histsize)"
        fi
    fi
}

# Test key functions
test_functions() {
    log_info "Testing key functions..."
    
    # Test if we can source the config without errors
    if zsh -c 'source ~/.zshrc' 2>/dev/null; then
        log_success "Zsh configuration loads without errors"
    else
        log_error "Zsh configuration has syntax errors"
        return 1
    fi
    
    # Test if history functions are available
    if zsh -c 'source ~/.zshrc; type fh' >/dev/null 2>&1; then
        log_success "fh function is available"
    else
        log_warning "fh function not available"
    fi
    
    if zsh -c 'source ~/.zshrc; type history_stats' >/dev/null 2>&1; then
        log_success "history_stats function is available"
    else
        log_warning "history_stats function not available"
    fi
    
    return 0
}

# Main verification function
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                  Dotfiles Verification                      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    local total_issues=0
    
    # Run all checks
    check_zsh_config || ((total_issues+=$?))
    echo ""
    
    check_tmux_config || ((total_issues+=$?))
    echo ""
    
    check_git_config || ((total_issues+=$?))
    echo ""
    
    check_scripts || ((total_issues+=$?))
    echo ""
    
    check_optional_tools
    echo ""
    
    check_environment
    echo ""
    
    test_functions || ((total_issues++))
    echo ""
    
    # Summary
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    Verification Summary                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    
    if [[ $total_issues -eq 0 ]]; then
        log_success "All core components are properly installed! 🎉"
        echo ""
        log_info "You can now:"
        echo "  • Use 'fh' for fuzzy history search"
        echo "  • Use 'hs' for history statistics"
        echo "  • Run '~/.dotfiles/scripts/history_maintenance.sh' for history management"
        echo "  • Restart your terminal or run 'source ~/.zshrc' to apply changes"
    else
        log_error "Found $total_issues issue(s) that need attention"
        echo ""
        log_info "To fix issues:"
        echo "  • Re-run the installer: ./install.sh"
        echo "  • Check file permissions: chmod +x ~/.dotfiles/scripts/*.sh"
        echo "  • Verify zsh syntax: zsh -n ~/.zshrc"
    fi
    
    exit $total_issues
}

# Run verification
main "$@"
