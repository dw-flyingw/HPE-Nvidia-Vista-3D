#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-vista3d}"
RELEASE_NAME="${RELEASE_NAME:-vista3d}"

echo -e "${GREEN}=== Vista3D MicroK8s Stop Script ===${NC}\n"

# Check if MicroK8s is installed
if ! command -v microk8s &> /dev/null; then
    echo -e "${RED}Error: MicroK8s is not installed.${NC}"
    exit 1
fi

# Configure kubectl for MicroK8s
export KUBECONFIG=$(microk8s config)

# Check if Helm release exists
if helm list -n "$NAMESPACE" 2>/dev/null | grep -q "$RELEASE_NAME"; then
    echo -e "${GREEN}[1/2] Uninstalling Helm release...${NC}"
    helm uninstall "$RELEASE_NAME" -n "$NAMESPACE"
    echo "  ✓ Helm release uninstalled"
else
    echo -e "${YELLOW}  No Helm release '$RELEASE_NAME' found in namespace '$NAMESPACE'${NC}"
fi

# Optional: Stop MicroK8s
echo -e "\n${GREEN}[2/2] MicroK8s status...${NC}"
read -p "Stop MicroK8s? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Stopping MicroK8s..."
    microk8s stop
    echo "  ✓ MicroK8s stopped"
else
    echo "  MicroK8s will continue running"
fi

echo -e "\n${GREEN}=== Stop Complete ===${NC}"
echo "Note: Namespace '$NAMESPACE' and PVCs were not deleted."
echo "To fully clean up, run:"
echo "  microk8s kubectl delete namespace $NAMESPACE"

