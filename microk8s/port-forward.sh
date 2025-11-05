#!/bin/bash

# Configuration
NAMESPACE="${NAMESPACE:-vista3d}"
RELEASE_NAME="${RELEASE_NAME:-vista3d}"

# PID file for tracking port-forward processes
PID_FILE="/tmp/vista3d-port-forward.pids"

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping port-forwards..."
    if [ -f "$PID_FILE" ]; then
        while read pid; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Stopping PID $pid..."
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    # Also kill any remaining kubectl port-forward processes
    pkill -f "kubectl port-forward.*vista3d" || true
    echo "All port-forwards stopped."
    exit 0
}

# Trap signals to cleanup
trap cleanup SIGINT SIGTERM EXIT

# Clear any existing PID file
rm -f "$PID_FILE"

echo "Starting port-forwards for Vista3D services..."
echo ""

# Start Frontend port-forward
echo "Starting port-forward for Frontend (8501)..."
microk8s kubectl port-forward service/${RELEASE_NAME}-frontend 8501:8501 -n ${NAMESPACE} > /dev/null 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >> "$PID_FILE"
echo "  Frontend port-forward PID: $FRONTEND_PID"
sleep 1

# Start Image Server port-forward
echo "Starting port-forward for Image Server (8888)..."
microk8s kubectl port-forward service/${RELEASE_NAME}-image-server 8888:8888 -n ${NAMESPACE} > /dev/null 2>&1 &
IMAGE_SERVER_PID=$!
echo "$IMAGE_SERVER_PID" >> "$PID_FILE"
echo "  Image Server port-forward PID: $IMAGE_SERVER_PID"
sleep 1

# Start Backend port-forward
echo "Starting port-forward for Backend (8000)..."
microk8s kubectl port-forward service/${RELEASE_NAME}-backend 8000:8000 -n ${NAMESPACE} > /dev/null 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >> "$PID_FILE"
echo "  Backend port-forward PID: $BACKEND_PID"
sleep 1

echo ""
echo "All port-forwards started successfully!"
echo ""
echo "Access the services at:"
echo "  Frontend (Streamlit):    http://localhost:8501"
echo "  Image Server:            http://localhost:8888"
echo "  Backend (Vista3D API):   http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all port-forwards."
echo ""

# Keep the script alive and monitor processes
while true; do
    # Check if all processes are still running
    all_running=true
    while read pid; do
        if ! kill -0 "$pid" 2>/dev/null; then
            all_running=false
            break
        fi
    done < "$PID_FILE"
    
    if [ "$all_running" = false ]; then
        echo "Warning: One or more port-forwards have stopped."
        cleanup
        exit 1
    fi
    
    sleep 5
done
