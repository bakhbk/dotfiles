#!/bin/bash

# Script to install basic-bashrc into a selected running Docker container or all containers

BASHRC_FILE="$(dirname "$0")/basic-bashrc"
INSTALL_ALL=false

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            INSTALL_ALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [-a|--all] [-h|--help]"
            echo "  -a, --all    Install bashrc into all running containers"
            echo "  -h, --help   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH."
    exit 1
fi

# Get list of running containers
containers=$(docker ps --format "{{.Names}}" | sort)

if [ -z "$containers" ]; then
    echo "No running containers found."
    exit 1
fi

# Function to install bashrc into a container
install_bashrc() {
    local container_name=$1
    echo "Installing bashrc into container: $container_name"
    
    docker cp "$BASHRC_FILE" "$container_name:/tmp/basic_bashrc.sh" && \
    docker exec "$container_name" bash -c "echo 'export CONTAINER_NAME=\"$container_name\"' > ~/.bashrc && cat /tmp/basic_bashrc.sh >> ~/.bashrc && rm /tmp/basic_bashrc.sh" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully installed into $container_name"
        return 0
    else
        echo "✗ Failed to install into $container_name"
        return 1
    fi
}

# Install into all containers if flag is set
if [ "$INSTALL_ALL" = true ]; then
    echo "Installing bashrc into all running containers..."
    echo ""
    
    success_count=0
    fail_count=0
    
    while IFS= read -r container_name; do
        if install_bashrc "$container_name"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
    done <<< "$containers"
    
    echo ""
    echo "Installation completed: $success_count succeeded, $fail_count failed"
    echo "Run 'source ~/.bashrc' in containers to apply changes."
    exit 0
fi

# Interactive selection for single container
echo "Running containers:"
echo "ID | Name"
echo "-----------------------------"

# Display containers with numbers
i=1
container_list=()
while IFS= read -r container_name; do
    echo "$i) $container_name"
    container_list+=("$container_name")
    ((i++))
done <<< "$containers"

# Prompt user to select
read -p "Select a container (1-$((i-1))): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt $((i-1)) ]; then
    echo "Invalid choice."
    exit 1
fi

# Get container name
selected_container="${container_list[$((choice-1))]}"

# Install bashrc
install_bashrc "$selected_container"

if [ $? -eq 0 ]; then
    echo "Run 'source ~/.bashrc' in the container to apply changes."
else
    echo "Installation failed."
    exit 1
fi