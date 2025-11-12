#!/bin/bash
# This script sets up the necessary storage for the Vista3D application on a Rancher-managed
# Kubernetes cluster and redeploys the application. It also sets up port-forwarding.

set -e
SCRIPT_DIR=$(dirname "$0")

echo ">>> This script will:"
echo "    1. Deploy the Rancher local-path storage provisioner."
echo "    2. Clean up any old Vista3D deployments and pending storage claims."
echo "    3. Redeploy the Vista3D application using vista3d.yaml."
echo "    4. Set up port-forwarding from your local machine to the application."
echo ""
read -p "Press [Enter] to continue or Ctrl+C to cancel..."

# --- 1. Deploy local-path-provisioner ---
echo ""
echo ">>> [1/5] Deploying Rancher's local-path provisioner..."
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
echo "Waiting for local-path-provisioner to be ready..."
kubectl rollout status deployment/local-path-provisioner -n local-path-storage --timeout=2m
echo "Local-path provisioner is ready."

# --- 2. Clean up old resources ---
echo ""
echo ">>> [2/5] Deleting old deployment and pending PVCs to ensure a clean start..."
kubectl delete deployment vista3d-frontend --ignore-not-found=true
kubectl delete pvc vista3d-dicom-pvc vista3d-output-pvc --ignore-not-found=true
echo "Waiting for resources to terminate..."
sleep 10

# --- 3. Redeploy the Vista3D application ---
echo ""
echo ">>> [3/5] Redeploying the Vista3D application..."
# Assuming this script is run from the 'rancher' directory
kubectl apply -f "$SCRIPT_DIR/vista3d.yaml"

# --- 4. Wait for the deployment to be ready ---
echo ""
echo ">>> [4/5] Waiting for the vista3d-frontend deployment to be ready..."
kubectl rollout status deployment/vista3d-frontend --timeout=5m
echo "Vista3D frontend is ready."

# --- 5. Set up port-forwarding ---
echo ""
echo ">>> [5/5] Setting up port-forwarding for the frontend service..."

# Kill any existing port-forward process
if [ -f .port_forward.pid ]; then
    echo "Stopping existing port-forward process..."
    kill $(cat .port_forward.pid) >/dev/null 2>&1 || true
    rm .port_forward.pid
fi

# Start port-forwarding in the background
kubectl port-forward service/vista3d-frontend 8501:8501 &
PORT_FORWARD_PID=$!
echo $PORT_FORWARD_PID > .port_forward.pid

echo "-----------------------------------------------------------------"
echo "✅ Setup complete!"
echo ""
echo "   You can now access the Vista3D frontend at: http://localhost:8501"
echo ""
echo "   The port-forwarding is running in the background (PID: $PORT_FORWARD_PID)."
echo "   To stop it, run from the 'rancher' directory: './stop_port_forward.sh'"
echo "-----------------------------------------------------------------"
