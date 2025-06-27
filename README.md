# Dotfiles

Enhanced configuration files and useful scripts for macOS and Linux with advanced history management and modern shell features.

## ✨ Features

- 🔧 **Enhanced History Management**: Smart history with fuzzy search, statistics, and automatic backups
- ⚡ **Modern Shell Experience**: Optimized zsh configuration with Oh My Zsh integration
- 🛠️ **Comprehensive Tooling**: Git helpers, tmux sessions, and development utilities
- 🔄 **Easy Management**: Install, update, verify, and uninstall scripts
- 📊 **History Analytics**: Command usage statistics and smart search capabilities
- 🔒 **Backup & Recovery**: Automatic backups with safe restoration options

## 🚀 Quick Installation

```bash
# Clone and install
git clone <your-repo-url> ~/.dotfiles-temp
cd ~/.dotfiles-temp
./install.sh

# Or install without optional tools
./install.sh --no-optional
```

## 📋 Available Scripts

### Installation & Management
- `./install.sh` - Main installer with interactive setup
- `./scripts/update.sh` - Update existing installation
- `./scripts/uninstall.sh` - Safe removal with backup restoration
- `./scripts/verify_installation.sh` - Verify installation integrity

### History Management
- `./scripts/history_maintenance.sh` - Comprehensive history management
  - `backup` - Create history backup
  - `dedupe` - Remove duplicate entries
  - `analyze` - Show usage statistics
  - `clean` - Clear history (with confirmation)

## 🔧 Configuration Files

### Core Shell Configuration
- `.zshrc` - Main zsh configuration
- `.zsh_aliases` - Custom aliases
- `.zsh_tools` - Utility functions
- `.zsh_history_config` - Advanced history features
- `.zshenv` - Environment variables
- `.shell_prompt` - Custom prompt configuration

### Development Tools
- `.tmux.conf` - Tmux configuration
- `git/` - Git configuration and helpers
- Various installation scripts for tools

## 🎯 New History Features

### Enhanced Commands
- `fh` - Fuzzy history search with fzf
- `hs` - History statistics
- `sl` - Execute last command with sudo
- `efh` - Execute command from history
- `lc [N]` - Show last N commands

### Smart Navigation
- `↑/↓` - History search with context
- `Ctrl+R` - Interactive fuzzy search
- History verification before execution

### Automatic Features
- Daily history backups
- Duplicate removal
- Timestamp tracking
- Command categorization

## 🛠️ Installation Options

```bash
# Full installation with prompts
./install.sh

# Skip backup creation
./install.sh --no-backup

# Skip optional tools installation
./install.sh --no-optional

# Get help
./install.sh --help
```

## 🔄 Updating

```bash
# Update from git and refresh configs
./scripts/update.sh

# Skip git update
./scripts/update.sh --skip-git

# Skip verification
./scripts/update.sh --skip-verification
```

## 🧪 Verification

```bash
# Check installation integrity
./scripts/verify_installation.sh
```

This will verify:
- ✅ All config files are present
- ✅ Scripts are executable
- ✅ Functions are available
- ✅ Environment is properly configured

## 🗂️ History Management

```bash
# Show statistics
./scripts/history_maintenance.sh stats

# Remove duplicates
./scripts/history_maintenance.sh dedupe

# Create backup
./scripts/history_maintenance.sh backup

# Analyze usage patterns
./scripts/history_maintenance.sh analyze
```

## 🛡️ Safe Uninstallation

```bash
# Interactive uninstall with backup restoration
./scripts/uninstall.sh

# Auto-confirm with history preservation
./scripts/uninstall.sh --yes --keep-history
```

## 📁 Directory Structure

```
~/.dotfiles/
├── history_backups/           # Automatic history backups
├── scripts/
│   ├── history_maintenance.sh # History management
│   ├── update.sh             # Update script
│   ├── verify_installation.sh # Verification
│   └── uninstall.sh          # Safe removal
├── .zsh_history_config       # Enhanced history features
└── [other config files]
```

## 🎨 Customization

### History Settings
Edit `~/.dotfiles/.zsh_history_config` to customize:
- History search behavior
- Ignored commands
- Backup frequency
- Statistics display

### Aliases and Functions
Add your custom aliases to `~/.dotfiles/.zsh_aliases`

### Environment Variables
Set environment variables in `~/.dotfiles/.zshenv`

## 🔍 Troubleshooting

### Common Issues

1. **Functions not available**
   ```bash
   source ~/.zshrc
   ./scripts/verify_installation.sh
   ```

2. **History not working**
   ```bash
   ./scripts/history_maintenance.sh backup
   ./scripts/history_maintenance.sh dedupe
   ```

3. **Permission issues**
   ```bash
   chmod +x ~/.dotfiles/scripts/*.sh
   ```

### Getting Help

- Run verification: `./scripts/verify_installation.sh`
- Check logs during installation
- Restore from backup if needed

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test your changes with verification script
4. Submit a pull request

## 📜 License

Based on [these sources](https://github.com/alkurbatov/dotfiles)

---

**Need help?** Run `./scripts/verify_installation.sh` to check your setup!
