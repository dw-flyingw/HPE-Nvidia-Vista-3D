#!/bin/bash
set -e

echo "Building and pushing Docker images for Vista3D..."

# Get the directory of the script
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# --- Build and push frontend image ---
echo ">>> Building frontend image..."
cd "$PROJECT_ROOT/frontend"
docker build -t dwtwp/vista3d-frontend:latest .
docker push dwtwp/vista3d-frontend:latest
echo "Frontend image built and pushed."

# --- Build and push image-server image ---
echo ">>> Building image-server image..."
cd "$PROJECT_ROOT/image_server"
docker build -t dwtwp/vista3d-image-server:latest .
docker push dwtwp/vista3d-image-server:latest
echo "Image-server image built and pushed."

echo "All images built and pushed successfully."
cd "$SCRIPT_DIR" # Return to the rancher directory
