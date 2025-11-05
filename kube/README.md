# Kubernetes Deployment

This folder contains scripts and configurations related to deploying the HPE-Nvidia-Vista-3D application to Kubernetes, specifically MicroK8s.

## Contents

- `notes.md`: MicroK8s setup and deployment guide
- `build_local_microk8s.sh`: Builds Docker images locally for MicroK8s (no external registry)
- `build_and_push_docker.sh`: Builds and pushes Docker images to Docker Hub
- `deploy_frontend.sh`: Deploys frontend and image-server to Kubernetes
- `port-forward.sh`: Port-forwarding utility for accessing services

## Usage

### Option 1: Build and Deploy (Default)

To build Docker images locally and deploy to MicroK8s:

```bash
./kube/deploy_frontend.sh
```

This will:
1. Build images locally using `build_local_microk8s.sh`
2. Deploy to the `vista3d` namespace
3. Wait for pods to be ready
4. Display port-forwarding instructions

### Option 2: Deploy Only (Skip Build)

If you already have built images and just want to deploy:

```bash
./kube/deploy_frontend.sh --skip-build
```

This will skip the build step and deploy existing images.

## MicroK8s Configuration

If you are using MicroK8s, ensure your `kubectl` is configured correctly. You can export the MicroK8s configuration and set the `KUBECONFIG` environment variable:

```bash
microk8s config > ~/.kube/config
export KUBECONFIG=~/.kube/config
```

To make the `KUBECONFIG` environment variable persistent, add the `export` command to your shell's configuration file (e.g., `~/.bashrc` or `~/.zshrc`).

## Accessing the Frontend

Once the `frontend` pod is running, you can access the web interface by port-forwarding:

```bash
# Manual port-forward
microk8s kubectl port-forward service/vista3d-frontend 8501:8501 -n vista3d

# Or use the convenience script
./kube/port-forward.sh
```

Then, open your browser to `http://localhost:8501`.

## Image Configuration

The deployment uses local Docker images (no external registry required):
- `vista3d-frontend:latest`
- `vista3d-image-server:latest`

Images are built locally using `build_local_microk8s.sh` and pulled by MicroK8s from the local Docker daemon.