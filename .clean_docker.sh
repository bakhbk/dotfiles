#!/bin/bash

ask() {
    echo "$1 (y/n)?"
    read -r answer
    case $answer in
        [Yy]|[Yy]es) return 0 ;;
        *) return 1 ;;
    esac
}

if [ "$1" = "-a" ]; then
    all=yes
else
    all=no
fi

# Stop all running containers, if any
if [ "$all" = "yes" ] || ask "Stop all running containers"; then
    if [ "$(docker ps -aq)" ]; then
        docker stop $(docker ps -aq)
    fi
fi

# Remove all containers, if any
if [ "$all" = "yes" ] || ask "Remove all containers"; then
    if [ "$(docker ps -aq)" ]; then
        docker rm $(docker ps -aq)
    fi
fi

# Remove all images, if any
if [ "$all" = "yes" ] || ask "Remove all images"; then
    if [ "$(docker images -q)" ]; then
        docker rmi $(docker images -q)
    fi
fi

# Remove all unused volumes
if [ "$all" = "yes" ] || ask "Remove all unused volumes"; then
    docker volume prune -f
fi

# Remove all unused networks
if [ "$all" = "yes" ] || ask "Remove all unused networks"; then
    docker network prune -f
fi

# Remove dangling images (images not used by any containers)
if [ "$all" = "yes" ] || ask "Remove dangling images"; then
    docker image prune -a -f
fi

# Remove Docker build cache
if [ "$all" = "yes" ] || ask "Remove Docker build cache"; then
    docker builder prune -a -f
fi

# Remove all volumes, including active ones
if [ "$all" = "yes" ] || ask "Remove all volumes, including active ones"; then
    docker volume rm $(docker volume ls -q) 2>/dev/null
fi

# Remove container logs
if [ "$all" = "yes" ] || ask "Remove container logs"; then
    docker run --rm -v /var/lib/docker/containers:/containers alpine sh -c 'find /containers -name "*.log" -delete' 2>/dev/null || true
fi

# Remove unused buildx builders
if [ "$all" = "yes" ] || ask "Remove unused buildx builders"; then
    docker buildx prune -a -f
fi

# Remove unused contexts (except default)
if [ "$all" = "yes" ] || ask "Remove unused contexts (except default)"; then
    docker context ls -q | grep -v default | xargs -r docker context rm 2>/dev/null || true
fi

# Remove all plugins
if [ "$all" = "yes" ] || ask "Remove all plugins"; then
    docker plugin ls -q | xargs -r docker plugin rm -f 2>/dev/null || true
fi

echo "Cleanup complete."

