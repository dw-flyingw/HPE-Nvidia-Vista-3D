#!/bin/bash
# Build Docker images specifically for MicroK8s deployment
# These images are optimized and verified for Kubernetes use

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VERSION="${1:-latest}"
REGISTRY="${2:-dwtwp}"
PUSH_IMAGES="${3:-no}"

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"
IMAGE_SERVER_DIR="$(cd "$(dirname "$0")/../image_server" && pwd)"

echo -e "${GREEN}=== Building MicroK8s Docker Images ===${NC}\n"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "Push images: $PUSH_IMAGES"
echo ""

# Ensure __init__.py exists in assets folder
if [ ! -f "$FRONTEND_DIR/assets/__init__.py" ]; then
    echo -e "${YELLOW}Creating missing __init__.py in assets folder...${NC}"
    touch "$FRONTEND_DIR/assets/__init__.py"
fi

# Build frontend image
echo -e "\n${GREEN}[1/2] Building frontend image...${NC}"
cd "$FRONTEND_DIR"
docker build -t "$REGISTRY/vista3d-frontend:microk8s-$VERSION" .
docker tag "$REGISTRY/vista3d-frontend:microk8s-$VERSION" "$REGISTRY/vista3d-frontend:microk8s-latest"

echo -e "${GREEN}✓ Frontend image built: $REGISTRY/vista3d-frontend:microk8s-$VERSION${NC}"

# Build image server
echo -e "\n${GREEN}[2/2] Building image server...${NC}"
cd "$IMAGE_SERVER_DIR"
docker build -t "$REGISTRY/vista3d-image-server:microk8s-$VERSION" .
docker tag "$REGISTRY/vista3d-image-server:microk8s-$VERSION" "$REGISTRY/vista3d-image-server:microk8s-latest"

echo -e "${GREEN}✓ Image server built: $REGISTRY/vista3d-image-server:microk8s-$VERSION${NC}"

# Push images if requested
if [ "$PUSH_IMAGES" = "yes" ]; then
    echo -e "\n${GREEN}Pushing images to registry...${NC}"
    docker push "$REGISTRY/vista3d-frontend:microk8s-$VERSION"
    docker push "$REGISTRY/vista3d-frontend:microk8s-latest"
    docker push "$REGISTRY/vista3d-image-server:microk8s-$VERSION"
    docker push "$REGISTRY/vista3d-image-server:microk8s-latest"
    echo -e "${GREEN}✓ Images pushed${NC}"
else
    echo -e "\n${YELLOW}Images built but not pushed. To push, run:${NC}"
    echo "  docker push $REGISTRY/vista3d-frontend:microk8s-$VERSION"
    echo "  docker push $REGISTRY/vista3d-frontend:microk8s-latest"
    echo "  docker push $REGISTRY/vista3d-image-server:microk8s-$VERSION"
    echo "  docker push $REGISTRY/vista3d-image-server:microk8s-latest"
fi

echo -e "\n${GREEN}=== Build Complete ===${NC}"
echo ""
echo "To use these images in MicroK8s, update helm/vista3d/values.yaml:"
echo "  frontend.image.tag: microk8s-$VERSION"
echo "  imageServer.image.tag: microk8s-$VERSION"
echo ""
echo "Or update the Helm release:"
echo "  helm upgrade vista3d helm/vista3d --namespace vista3d \\"
echo "    --set frontend.image.tag=microk8s-$VERSION \\"
echo "    --set imageServer.image.tag=microk8s-$VERSION"

