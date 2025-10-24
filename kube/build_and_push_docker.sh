#!/bin/bash

# Docker Build and Push Script for Vista3D
# This script builds and pushes both the image_server and frontend Docker images
# For Linux ARM64 platform

set -e  # Exit on error

# Configuration
DOCKER_USERNAME="mendeza"
VERSION="${1:-v1.0.0}"  # Default to v1.0.0 if no version specified
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Vista3D Docker Build and Push Script ===${NC}"
echo -e "Version: ${YELLOW}${VERSION}${NC}"
echo -e "Docker Username: ${YELLOW}${DOCKER_USERNAME}${NC}"
echo ""

# Check if logged into Docker Hub
echo -e "${YELLOW}Checking Docker Hub login...${NC}"
if ! grep -q "docker.io" ~/.docker/config.json 2>/dev/null; then
    echo -e "${RED}Not logged into Docker Hub. Please run: docker login${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Hub login confirmed${NC}"
echo ""

# Function to build and push an image
build_and_push() {
    local service_name=$1
    local service_path=$2
    local image_name="${DOCKER_USERNAME}/vista3d-${service_name}"
    
    echo -e "${GREEN}=== Building ${service_name} ===${NC}"
    cd "${PROJECT_ROOT}/${service_path}"
    
    echo "Building ${image_name}:${VERSION}..."
    docker build -t "${image_name}:${VERSION}" .
    
    echo "Tagging as latest..."
    docker tag "${image_name}:${VERSION}" "${image_name}:latest"
    
    echo "Pushing ${image_name}:${VERSION}..."
    docker push "${image_name}:${VERSION}"
    
    echo "Pushing ${image_name}:latest..."
    docker push "${image_name}:latest"
    
    echo -e "${GREEN}✓ Successfully built and pushed ${service_name}${NC}"
    echo ""
}

# Build and push image_server
build_and_push "image-server" "../image_server"

# Build and push frontend
build_and_push "frontend" "../frontend"

echo -e "${GREEN}=== All images built and pushed successfully! ===${NC}"
echo ""
echo "Images pushed:"
echo "  - ${DOCKER_USERNAME}/vista3d-image-server:${VERSION}"
echo "  - ${DOCKER_USERNAME}/vista3d-image-server:latest"
echo "  - ${DOCKER_USERNAME}/vista3d-frontend:${VERSION}"
echo "  - ${DOCKER_USERNAME}/vista3d-frontend:latest"

