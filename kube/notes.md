# Ubuntu Server microk8s Setup and Vista3D Deployment Guide

## Prerequisites
- Ubuntu 20.04+ server
- User with sudo privileges
- Internet connection

## Step 1: Install microk8s

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install microk8s
sudo snap install microk8s --classic

# Add current user to microk8s group
sudo usermod -a -G microk8s $USER

# Apply group changes (logout/login or use newgrp)
newgrp microk8s

# Verify installation
microk8s status --wait-ready
```

## Step 2: Configure microk8s

```bash
# Enable required addons
microk8s enable dns storage ingress

# Wait for addons to be ready
microk8s status --wait-ready

# Create kubeconfig file
microk8s config > ~/microk8s.kubeconfig

# Set KUBECONFIG environment variable
export KUBECONFIG=/home/hpadmin/HPE-Nvidia-Vista-3D/kube/microk8s.kubeconfig

# Verify cluster is working
microk8s kubectl get nodes
microk8s kubectl get pods --all-namespaces
```

## Step 3: Install Helm

```bash
# Download and install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify Helm installation
helm version
```

## Step 4: Deploy Vista3D Helm Chart

```bash
# Navigate to project directory
cd /path/to/HPE-Nvidia-Vista-3D

# Deploy Vista3D (frontend and image server only)
helm install vista3d helm/vista3d --namespace vista3d --create-namespace

# Wait for deployment to complete
microk8s kubectl get pods -n vista3d -w

# Check deployment status
microk8s kubectl get deployments -n vista3d
microk8s kubectl get services -n vista3d
```

## Step 5: Port Forwarding to Localhost

### Option A: Direct Port Forwarding (if accessing from Ubuntu server)

```bash
# Port forward frontend (Streamlit)
microk8s kubectl port-forward service/vista3d-frontend 8501:8501 -n vista3d &

# Port forward image server (FastAPI)
microk8s kubectl port-forward service/vista3d-image-server 8888:8888 -n vista3d &

# Access services
# Frontend: http://localhost:8501
# Image Server: http://localhost:8888
```

### Option B: SSH Tunnel from Local Machine

From your local machine (Mac/Windows), create SSH tunnel to access services:

```bash
# Create SSH tunnel to Ubuntu server
ssh -L 8501:localhost:8501 -L 8888:localhost:8888 username@ubuntu-server-ip

# Then on Ubuntu server, run port forwarding
microk8s kubectl port-forward service/vista3d-frontend 8501:8501 -n vista3d &
microk8s kubectl port-forward service/vista3d-image-server 8888:8888 -n vista3d &
```

## Step 6: Verify Deployment

```bash
# Check all pods are running
microk8s kubectl get pods -n vista3d

# Check services
microk8s kubectl get svc -n vista3d

# Check sample data installation job
microk8s kubectl get jobs -n vista3d

# View logs if needed
microk8s kubectl logs -l app.kubernetes.io/name=vista3d -n vista3d
```

## Step 7: Access the Application

1. **Frontend (Streamlit)**: http://localhost:8501
2. **Image Server API**: http://localhost:8888
3. **Sample Data**: Automatically installed during deployment

## Troubleshooting Commands

```bash
# Check microk8s status
microk8s status

# Restart microk8s if needed
microk8s stop
microk8s start

# Check Helm releases
helm list -n vista3d

# Uninstall and reinstall if needed
helm uninstall vista3d -n vista3d
helm install vista3d helm/vista3d --namespace vista3d --create-namespace

# Check persistent volumes
microk8s kubectl get pvc -n vista3d

# Check sample data job logs
microk8s kubectl logs -l app.kubernetes.io/component=sample-data-init -n vista3d
```

## Cleanup Commands

```bash
# Uninstall Vista3D
helm uninstall vista3d -n vista3d

# Delete namespace (optional)
microk8s kubectl delete namespace vista3d

# Stop microk8s
microk8s stop
```
