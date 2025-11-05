#!/bin/bash

# Script to deploy the frontend and image-server to MicroK8s
# Usage: ./kube/deploy_frontend.sh [--skip-build]

set -e # Exit on error

# Parse arguments
SKIP_BUILD=false
if [[ "$1" == "--skip-build" ]]; then
    SKIP_BUILD=true
fi

# Build images if not skipping
if [ "$SKIP_BUILD" = false ]; then
    echo "=== Building Docker images locally ==="
    VERSION=$(./kube/build_local_microk8s.sh latest)
    echo "Captured VERSION: ${VERSION}"
else
    echo "=== Skipping build (using existing images) ==="
    VERSION="latest"
fi

# Check if helm release exists
if helm status vista3d -n vista3d &> /dev/null; then
    echo "=== Upgrading Helm release ==="
    helm upgrade vista3d ./helm/vista3d \
        --namespace vista3d \
        --set frontend.image.tag="${VERSION}" \
        --set imageServer.image.tag="${VERSION}"
else
    echo "=== Installing Helm release ==="
    helm install vista3d ./helm/vista3d \
        --namespace vista3d \
        --create-namespace \
        --set frontend.image.tag="${VERSION}" \
        --set imageServer.image.tag="${VERSION}"
fi

echo "=== Waiting for pods to be ready ==="
microk8s kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/component=frontend \
    -n vista3d \
    --timeout=300s || true

microk8s kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/component=image-server \
    -n vista3d \
    --timeout=300s || true

echo "=== Deployment process complete ==="
echo ""
echo "To check pod status:"
echo "  microk8s kubectl get pods -n vista3d"
echo ""
echo "To port-forward and access the web interface:"
echo "  microk8s kubectl port-forward service/vista3d-frontend 8501:8501 -n vista3d"
echo ""
echo "Or use the port-forward script:"
echo "  ./kube/port-forward.sh"