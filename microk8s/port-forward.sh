#!/bin/bash

echo "Starting port-forward for Frontend (8501)..."
microk8s kubectl port-forward service/vista3d-frontend 8501:8501 -n vista3d &
FRONTEND_PID=$!
echo "Frontend port-forward PID: $FRONTEND_PID"

echo "Starting port-forward for Image Server (8888)..."
microk8s kubectl port-forward service/vista3d-image-server 8888:8888 -n vista3d &
IMAGE_SERVER_PID=$!
echo "Image Server port-forward PID: $IMAGE_SERVER_PID"

echo "All port-forwards started in the background."
echo "To stop them, use 'kill $FRONTEND_PID $IMAGE_SERVER_PID' or 'killall kubectl'."
echo "Keeping script alive. Press Ctrl+C to exit this script (this will NOT stop the port-forwards)."

# Keep the script alive so the background processes don't get killed immediately
sleep 10
