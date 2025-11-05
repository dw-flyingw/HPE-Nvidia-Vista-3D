#!/bin/bash

# Docker Local Build Script for Vista3D on MicroK8s
# This script builds both the image_server and frontend Docker images locally
# No pushing to external registries - images are for local MicroK8s use

set -e  # Exit on error

# Configuration
VERSION="${1:-latest}"  # Default to latest if no version specified
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Vista3D Local Docker Build Script ===${NC}"
echo -e "Version: ${YELLOW}${VERSION}${NC}"
echo ""

# Function to build an image
build_image() {
    local service_name=$1
    local service_path=$2
    local image_name="vista3d-${service_name}"
    
    echo -e "${GREEN}=== Building ${service_name} ===${NC}"
    cd "${PROJECT_ROOT}/${service_path}"
    
    echo "Building ${image_name}:${VERSION}..."
    docker build -t "${image_name}:${VERSION}" .
    
    echo "Tagging as latest..."
    docker tag "${image_name}:${VERSION}" "${image_name}:latest"
    
    echo -e "${GREEN}✓ Successfully built ${service_name}${NC}"
    echo ""
}

# Build frontend
build_image "image-server" "../image_server"

# Build frontend
build_image "frontend" "../frontend"

echo -e "${GREEN}=== All images built successfully! ===${NC}"
echo ""
echo "Images built:"
echo "  - vista3d-image-server:${VERSION}"
echo "  - vista3d-image-server:latest"
echo "  - vista3d-frontend:${VERSION}"
echo "  - vista3d-frontend:latest"
echo ""
echo "Ready for deployment with: ./kube/deploy_frontend.sh"

# Return the version for the calling script
echo "${VERSION}"

