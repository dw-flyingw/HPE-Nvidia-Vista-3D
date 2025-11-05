#!/bin/bash
# Temporary fix: Create ConfigMap from assets folder and mount it in frontend pod

set -e

NAMESPACE="${NAMESPACE:-vista3d}"
FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "Creating ConfigMap from assets folder..."

# Create ConfigMap from assets directory
microk8s kubectl create configmap vista3d-frontend-assets \
  --from-file="$FRONTEND_DIR/assets" \
  -n "$NAMESPACE" \
  --dry-run=client -o yaml | microk8s kubectl apply -f -

echo "ConfigMap created. You'll need to update the frontend deployment to mount it."
echo "Add this volumeMount and volume to the frontend deployment:"
echo ""
echo "volumeMounts:"
echo "  - name: assets"
echo "    mountPath: /app/assets"
echo ""
echo "volumes:"
echo "  - name: assets"
echo "    configMap:"
echo "      name: vista3d-frontend-assets"

