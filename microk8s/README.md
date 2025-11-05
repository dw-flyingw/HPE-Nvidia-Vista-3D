# Vista3D MicroK8s Deployment

This directory contains scripts and Helm charts for deploying Vista3D on Ubuntu servers with MicroK8s and NVIDIA GPUs.

## Prerequisites

- Ubuntu 20.04+ server
- 2x NVIDIA H200 GPUs (or compatible)
- User with sudo privileges
- Internet connection
- MicroK8s installed (or will be installed by script)

## Quick Start

### 1. Install MicroK8s (if not already installed)

```bash
sudo snap install microk8s --classic
sudo usermod -a -G microk8s $USER
newgrp microk8s  # or log out and back in
```

### 2. Set NGC API Key (Required for backend)

```bash
export NGC_API_KEY="nvapi-your-api-key-here"
```

### 3. Start Deployment

```bash
cd microk8s
./start.sh
```

The script will:
- Start MicroK8s if not running
- Enable required addons (dns, storage, ingress, host-access, nvidia)
- Verify GPU availability
- Create namespace
- Deploy Vista3D using Helm chart
- Wait for pods to be ready

### 4. Access Services

Use port forwarding to access the services:

```bash
# Frontend (Streamlit)
microk8s kubectl port-forward svc/vista3d-frontend 8501:8501 -n vista3d

# Image Server
microk8s kubectl port-forward svc/vista3d-image-server 8888:8888 -n vista3d

# Backend (Vista3D API)
microk8s kubectl port-forward svc/vista3d-backend 8000:8000 -n vista3d
```

Then open:
- Frontend: http://localhost:8501
- Image Server: http://localhost:8888
- Backend API: http://localhost:8000

## Stop Deployment

```bash
./stop.sh
```

This will:
- Uninstall the Helm release
- Optionally stop MicroK8s

## Configuration

### Environment Variables

The start script uses these environment variables:

- `NAMESPACE` - Kubernetes namespace (default: `vista3d`)
- `RELEASE_NAME` - Helm release name (default: `vista3d`)
- `NGC_API_KEY` - NVIDIA NGC API key (required for backend)

### Customizing Deployment

Edit `helm/vista3d/values.yaml` to customize:
- Resource limits and requests
- Replica counts
- Image tags
- Storage sizes
- Environment variables

Then redeploy:

```bash
cd microk8s
helm upgrade vista3d helm/vista3d --namespace vista3d
```

## Helm Chart

The Helm chart is located in `helm/vista3d/` and includes:

- **Backend**: NVIDIA NIM Vista3D container with GPU support
- **Frontend**: Streamlit application
- **Image Server**: FastAPI server for serving medical images
- **Persistent Volumes**: For output and DICOM data

### Deploying with Helm Directly

```bash
# Set NGC API key
export NGC_API_KEY="your-key"

# Deploy
helm install vista3d helm/vista3d \
  --namespace vista3d \
  --create-namespace \
  --set secrets.ngcApiKey="$NGC_API_KEY"

# Upgrade
helm upgrade vista3d helm/vista3d \
  --namespace vista3d \
  --set secrets.ngcApiKey="$NGC_API_KEY"

# Uninstall
helm uninstall vista3d --namespace vista3d
```

## Troubleshooting

### Check Pod Status

```bash
microk8s kubectl get pods -n vista3d
microk8s kubectl describe pod <pod-name> -n vista3d
microk8s kubectl logs <pod-name> -n vista3d
```

### Check GPU Availability

```bash
microk8s kubectl get nodes -o json | grep nvidia.com/gpu
```

### Check Services

```bash
microk8s kubectl get svc -n vista3d
```

### Restart MicroK8s

```bash
microk8s stop
microk8s start
```

### View All Resources

```bash
microk8s kubectl get all -n vista3d
```

## Network Configuration

The deployment uses Kubernetes internal service names for communication:

- Frontend → Backend: `http://vista3d-backend:8000`
- Frontend → Image Server: `http://vista3d-image-server:8888`
- Backend → Image Server: `http://vista3d-image-server:8888`

These are automatically configured via environment variables in the Helm chart.

## Storage

The deployment creates PersistentVolumeClaims for:
- Output data (100Gi, ReadWriteOnce)
- DICOM data (50Gi, ReadOnlyMany)
- Frontend code (1Gi, ReadWriteOnce)

Data persists across pod restarts and deployments.

## Notes

- The scripts are simple and don't include extensive error handling or rollback logic
- GPU resources are allocated per the values in `values.yaml` (default: 1 GPU per backend pod)
- For 2 H200 GPUs, you can scale backend replicas or adjust resource allocation in values.yaml

