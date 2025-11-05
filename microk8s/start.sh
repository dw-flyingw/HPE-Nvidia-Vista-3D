#!/bin/bash
set -e

# Ensure we're running with bash, not sh
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-vista3d}"
RELEASE_NAME="${RELEASE_NAME:-vista3d}"
HELM_CHART_DIR="$(cd "$(dirname "$0")" && pwd)/helm/vista3d"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Ensure /snap/bin is in PATH (needed for snap-installed tools like microk8s)
if [[ ":$PATH:" != *":/snap/bin:"* ]]; then
    export PATH="$PATH:/snap/bin"
fi

echo -e "${GREEN}=== Vista3D MicroK8s Deployment Script ===${NC}\n"

# Check if MicroK8s is installed
if ! command -v microk8s &> /dev/null; then
    echo -e "${RED}Error: MicroK8s is not installed.${NC}"
    echo "Please install MicroK8s first:"
    echo "  sudo snap install microk8s --classic"
    exit 1
fi

# Check if user is in microk8s group
if ! groups | grep -q microk8s; then
    echo -e "${YELLOW}Warning: Current user is not in microk8s group.${NC}"
    echo "You may need to run: sudo usermod -a -G microk8s $USER"
    echo "Then log out and back in, or run: newgrp microk8s"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start MicroK8s if not running
echo -e "${GREEN}[1/7] Checking MicroK8s status...${NC}"
if ! microk8s status --wait-ready &> /dev/null; then
    echo "Starting MicroK8s..."
    microk8s start
    microk8s status --wait-ready
else
    echo "MicroK8s is already running"
fi

# Enable required addons
echo -e "\n${GREEN}[2/7] Enabling MicroK8s addons...${NC}"
ADDONS="dns storage ingress host-access"
for addon in $ADDONS; do
    if microk8s status | grep -q "$addon: enabled"; then
        echo "  ✓ $addon already enabled"
    else
        echo "  Enabling $addon..."
        microk8s enable $addon
    fi
done

# Enable NVIDIA GPU support
echo -e "\n${GREEN}[3/7] Enabling NVIDIA GPU support...${NC}"
if microk8s status | grep -q "nvidia: enabled"; then
    echo "  ✓ NVIDIA support already enabled"
else
    echo "  Enabling NVIDIA device plugin..."
    microk8s enable nvidia
    echo "  Waiting for NVIDIA plugin to be ready..."
    sleep 10
fi

# Verify GPU availability
echo -e "\n${GREEN}[4/7] Verifying GPU availability...${NC}"
if microk8s kubectl get nodes -o json | grep -q "nvidia.com/gpu"; then
    GPU_COUNT=$(microk8s kubectl get nodes -o jsonpath='{.items[0].status.allocatable.nvidia\.com/gpu}')
    echo "  ✓ GPUs detected: $GPU_COUNT"
else
    echo -e "${YELLOW}  Warning: No GPUs detected in cluster.${NC}"
    echo "  This may be normal if GPUs haven't been discovered yet."
fi

# Create namespace if it doesn't exist
echo -e "\n${GREEN}[5/7] Creating namespace...${NC}"
if microk8s kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "  ✓ Namespace '$NAMESPACE' already exists"
else
    echo "  Creating namespace '$NAMESPACE'..."
    microk8s kubectl create namespace "$NAMESPACE"
fi

# Check for NGC API key
echo -e "\n${GREEN}[6/7] Checking NGC API key...${NC}"
if [ -z "$NGC_API_KEY" ]; then
    echo -e "${YELLOW}  NGC_API_KEY environment variable not set.${NC}"
    read -p "  Enter your NGC API key (or press Enter to skip and set later): " NGC_API_KEY
    if [ -z "$NGC_API_KEY" ]; then
        echo -e "${YELLOW}  Warning: NGC API key not provided. Backend will not work without it.${NC}"
        echo "  You can set it later with:"
        echo "    export NGC_API_KEY=your-key"
        echo "    microk8s kubectl create secret generic vista3d-secrets --from-literal=ngc-api-key=\$NGC_API_KEY -n $NAMESPACE"
    fi
fi

# Note: Secret will be created by Helm chart if NGC_API_KEY is provided
if [ -n "$NGC_API_KEY" ]; then
    echo "  ✓ NGC API key provided - will be set in Helm deployment"
fi

# Check if Helm is available
echo -e "\n${GREEN}[7/7] Checking Helm installation...${NC}"
if ! command -v helm &> /dev/null; then
    echo "  Helm not found. Installing Helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Configure kubectl for MicroK8s
export KUBECONFIG=$(microk8s config)

# Deploy with Helm
echo -e "\n${GREEN}Deploying Vista3D with Helm...${NC}"
cd "$SCRIPT_DIR"

if helm list -n "$NAMESPACE" | grep -q "$RELEASE_NAME"; then
    echo "  Release '$RELEASE_NAME' already exists. Upgrading..."
    helm upgrade "$RELEASE_NAME" "$HELM_CHART_DIR" \
        --namespace "$NAMESPACE" \
        ${NGC_API_KEY:+--set secrets.ngcApiKey="$NGC_API_KEY"}
else
    echo "  Installing release '$RELEASE_NAME'..."
    helm install "$RELEASE_NAME" "$HELM_CHART_DIR" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        ${NGC_API_KEY:+--set secrets.ngcApiKey="$NGC_API_KEY"}
fi

# Wait for pods to be ready
echo -e "\n${GREEN}Waiting for pods to be ready...${NC}"
microk8s kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/instance="$RELEASE_NAME" \
    -n "$NAMESPACE" \
    --timeout=300s || {
    echo -e "${YELLOW}Some pods may not be ready yet. Check status with:${NC}"
    echo "  microk8s kubectl get pods -n $NAMESPACE"
}

# Display status
echo -e "\n${GREEN}=== Deployment Status ===${NC}"
microk8s kubectl get pods -n "$NAMESPACE"
echo ""

# Display services
echo -e "${GREEN}=== Services ===${NC}"
microk8s kubectl get svc -n "$NAMESPACE"
echo ""

# Display access information
echo -e "${GREEN}=== Access Information ===${NC}"
echo "To access the services, use port forwarding:"
echo ""
echo "  Frontend (Streamlit):"
echo "    microk8s kubectl port-forward svc/$RELEASE_NAME-frontend 8501:8501 -n $NAMESPACE"
echo "    Then open: http://localhost:8501"
echo ""
echo "  Image Server:"
echo "    microk8s kubectl port-forward svc/$RELEASE_NAME-image-server 8888:8888 -n $NAMESPACE"
echo "    Then open: http://localhost:8888"
echo ""
echo "  Backend (Vista3D API):"
echo "    microk8s kubectl port-forward svc/$RELEASE_NAME-backend 8000:8000 -n $NAMESPACE"
echo "    Then open: http://localhost:8000"
echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"

