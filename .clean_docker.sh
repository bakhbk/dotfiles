#!/bin/bash

# Stop all running containers, if any
if [ "$(docker ps -aq)" ]; then
  docker stop $(docker ps -aq)
fi

# Remove all containers, if any
if [ "$(docker ps -aq)" ]; then
  docker rm $(docker ps -aq)
fi

# Remove all images, if any
if [ "$(docker images -q)" ]; then
  docker rmi $(docker images -q)
fi

# Remove all unused volumes
docker volume prune -f

# Remove all unused networks
docker network prune -f

# Remove dangling images (images not used by any containers)
docker image prune -a -f

# Remove Docker build cache
docker builder prune -a -f

# Remove all volumes, including active ones
docker volume rm $(docker volume ls -q) 2>/dev/null

