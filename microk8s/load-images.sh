#!/bin/bash
# Load locally built MicroK8s images into MicroK8s without pushing to registry

set -e

# Ensure we're running with bash
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REGISTRY="${1:-dwtwp}"
VERSION="${2:-latest}"

FRONTEND_IMAGE="$REGISTRY/vista3d-frontend:microk8s-$VERSION"
IMAGE_SERVER_IMAGE="$REGISTRY/vista3d-image-server:microk8s-$VERSION"

echo -e "${GREEN}=== Loading Images into MicroK8s ===${NC}\n"

# Check if images exist (use docker images to check, more reliable)
if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${FRONTEND_IMAGE}$"; then
    echo -e "${YELLOW}Error: Frontend image not found: $FRONTEND_IMAGE${NC}"
    echo "Available images:"
    docker images | grep vista3d || echo "  (none found)"
    echo ""
    echo "Please build the images first with: ./build-images.sh"
    exit 1
fi

if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_SERVER_IMAGE}$"; then
    echo -e "${YELLOW}Error: Image server image not found: $IMAGE_SERVER_IMAGE${NC}"
    echo "Available images:"
    docker images | grep vista3d || echo "  (none found)"
    echo ""
    echo "Please build the images first with: ./build-images.sh"
    exit 1
fi

# Load frontend image
echo -e "${GREEN}[1/2] Loading frontend image...${NC}"
docker save "$FRONTEND_IMAGE" | microk8s ctr image import -
echo "  ✓ Frontend image loaded"

# Load image server
echo -e "\n${GREEN}[2/2] Loading image server...${NC}"
docker save "$IMAGE_SERVER_IMAGE" | microk8s ctr image import -
echo "  ✓ Image server loaded"

echo -e "\n${GREEN}=== Load Complete ===${NC}"
echo ""
echo "Images are now available in MicroK8s. You can deploy with:"
echo "  ./start.sh"
echo ""
echo "Or upgrade existing deployment:"
echo "  helm upgrade vista3d helm/vista3d --namespace vista3d \\"
echo "    --set frontend.image.tag=microk8s-$VERSION \\"
echo "    --set imageServer.image.tag=microk8s-$VERSION"

