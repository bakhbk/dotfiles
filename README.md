# Dotfiles

Configuration files and useful scripts for OS X and Linux.

## Installation

```bash
# To install common configuration files on localhost do:
$ ./install.sh
```

## Docker/OrbStack

### Install OrbStack (recommended for macOS)
```bash
# Install or update OrbStack with docker compose support
$ ./scripts/install_orbstack.sh
# or
$ ./.install_orbstack.sh
```

### Remove Docker Desktop (before installing OrbStack)
```bash
# Remove Docker Desktop cleanly
$ ./.remove_docker_desktop.sh
```

See [ORBSTACK.md](ORBSTACK.md) for detailed information.

Based on [these sources](https://github.com/alkurbatov/dotfiles)
