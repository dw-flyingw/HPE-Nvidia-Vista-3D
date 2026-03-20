# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HPE Medical Imaging AI Segmentation platform combining HPE High Performance Compute infrastructure with NVIDIA's Vista3D technology for automated vessel and anatomical structure segmentation on DICOM medical imaging data.

**Key Capabilities:**
- Automated AI-powered segmentation using NVIDIA Vista3D NIM
- 3D medical image visualization with NiiVue
- DICOM to NIfTI conversion
- Supports CT and MRI imaging (body structures, organs, vessels)
- **Limitation**: Not optimized for detailed brain structure segmentation

## Architecture

### Three-Component System

1. **Backend** (`backend/`) - Vista3D AI Server (GPU-required)
   - NVIDIA Vista3D NIM container (~30GB Docker image)
   - Requires NVIDIA GPU with CUDA support
   - Runs on port 8000
   - Handles AI segmentation inference

2. **Frontend** (`frontend/`) - Streamlit Web Application
   - Multi-page Streamlit app (ports 8501)
   - Pages: Home, Image Data, NiiVue Viewer, Tools
   - Docker containerized
   - Communicates with backend via HTTP

3. **Image Server** (`image_server/`) - FastAPI File Server
   - Serves DICOM/NIfTI files over HTTP (port 8888)
   - Required for Vista3D to access medical images
   - Docker containerized
   - Separate service from frontend

### Distributed Deployment Pattern

The platform is designed for **distributed deployment**:
- **Backend**: Remote Ubuntu GPU server
- **Frontend + Image Server**: Local Mac/workstation OR same remote server
- **Connection**: SSH tunnels for secure communication

**SSH Tunnel Command:**
```bash
ssh -L 8000:localhost:8000 -R 8888:0.0.0.0:8888 user@ubuntu-server
```
- `-L 8000:localhost:8000` - Forward tunnel: Access remote Vista3D
- `-R 8888:0.0.0.0:8888` - Reverse tunnel: Backend accesses local image server (MUST use 0.0.0.0)

### Traefik Path-Based Proxy Deployment

**Current Production Setup** (`/data/opt/Traefik/dynamic.yml`):
- **Homepage**: `https://moto.hst.rdlabs.hpecorp.net` (port 443 → gethomepage)
- **Vista3D Frontend**: `https://moto.hst.rdlabs.hpecorp.net/vista` (Traefik → localhost:8501)
- **Image Server**: `https://moto.hst.rdlabs.hpecorp.net/vista-images` (Traefik → localhost:8888)
- **SSL Termination**: At Traefik (port 443)
- **WebSocket Support**: Traefik v3 handles WebSocket upgrades automatically

**Streamlit Configuration:**

Streamlit `baseUrlPath = "/vista"` is set in `frontend/.streamlit/config.toml`. Traefik forwards `/vista/*` requests to Streamlit without stripping the prefix — Streamlit handles the prefix natively.

**Environment Variables for Traefik Proxy:**
```bash
# Frontend URLs (use public HTTPS URLs with Traefik path prefixes)
IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"
EXTERNAL_IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"

# Backend can still use localhost (all on same server)
VISTA3D_SERVER="http://localhost:8000"
VISTA3D_IMAGE_SERVER_URL="http://localhost:8888"

# Image server root path (Traefik strips /vista-images, ROOT_PATH adds it back in HTML links)
ROOT_PATH="/vista-images"
```

**Traefik Routing:**
- `/vista` → `http://host.docker.internal:8501` (no prefix strip — Streamlit handles via `baseUrlPath`)
- `/vista-images` → `http://host.docker.internal:8888` (prefix stripped by Traefik, `ROOT_PATH` for HTML links)

### Docker Network Architecture

**Traefik Path-Based Proxy Deployment (Current Setup):**
- **All containers**: Share `vista3d-network` (Docker network) for inter-container communication
- **Traefik**: Routes via `host.docker.internal` to reach containers on the host
- **Frontend + Image Server**: Inter-container communication via Docker hostnames

**Alternative Deployments:**
- **SSH Tunnel**: Same as reverse proxy - localhost communication
- **All-local (single Docker Compose)**: All containers share single Docker network
- Uses `host.docker.internal` for Mac Docker-to-host communication

## Development Commands

### Initial Setup

**Backend (GPU Ubuntu Server):**
```bash
cd backend
python3 setup.py
docker compose up -d
```

**Frontend (Mac or Linux):**
```bash
cd frontend
python3 setup.py
docker compose up -d  # Starts both frontend AND image server
```

### Daily Development

**Start Services:**
```bash
# Backend (on Ubuntu server)
cd backend && docker compose up -d

# Frontend + Image Server (on Mac/workstation)
cd frontend && docker compose up -d
```

**Stop Services:**
```bash
cd backend && docker compose down
cd frontend && docker compose down
```

**View Logs:**
```bash
# Backend
cd backend && docker compose logs -f

# Frontend
cd frontend && docker compose logs -f vista3d-frontend-standalone

# Image Server
cd frontend && docker compose logs -f vista3d-image-server-for-frontend
```

### Local Development (Without Docker)

**Frontend Development Environment:**
```bash
# Lightweight environment (no ML dependencies)
uv venv .venv-frontend
source .venv-frontend/bin/activate
uv pip install python-dotenv nibabel numpy tqdm requests beautifulsoup4 bs4 streamlit fastapi uvicorn pandas plotly dcm2niix vtk trimesh pymeshfix stl extra-streamlit-components scikit-image plyfile

# Run Streamlit app locally
cd frontend
streamlit run app.py
```

**Note:** The backend Vista3D server should still run in Docker (requires GPU + NVIDIA Container Toolkit).

## Key File Locations

### Configuration
- `.env` - Project root configuration (template/reference)
- `frontend/.env` - **Frontend Docker Compose configuration** (REQUIRED - used by frontend/docker-compose.yml)
- `backend/.env` - **Backend Docker Compose configuration** (REQUIRED - used by backend/docker-compose.yml)
- `frontend/conf/vista3d_label_colors.json` - Anatomical structure labels and colors (127+ structures)

**IMPORTANT**: Docker Compose reads `.env` from the same directory as `docker-compose.yml`. The project root `.env` is NOT read by Docker Compose. You must update `frontend/.env` and `backend/.env` separately.

### Data Directories
- `dicom/` - DICOM input files (patient folders: PA*, SER*)
- `output/{patient_id}/nifti/` - Converted NIfTI files
- `output/{patient_id}/voxels/{scan_name}/original/` - Segmentation results

### Frontend Code Structure
- `frontend/app.py` - Main Streamlit entry point with navigation
- `frontend/Image_Data.py` - Image data browser page
- `frontend/NiiVue_Viewer.py` - 3D viewer page
- `frontend/Tools.py` - Batch processing tools page
- `frontend/utils/` - Utility modules:
  - `segment.py` - Vista3D API client for segmentation
  - `dicom2nifti.py` - DICOM to NIfTI conversion
  - `config_manager.py` - Configuration and label management
  - `data_manager.py` - Image server API client
  - `voxel_manager.py` - Voxel data management
  - `viewer_config.py` - NiiVue viewer settings

### Backend Code
- `backend/docker-compose.yml` - Vista3D NIM container configuration
- `backend/setup.py` - Backend setup script

### Image Server Code
- `image_server/server.py` - FastAPI server implementation
- `image_server/docker-compose.yml` - Image server container config

## Environment Variables

### Configuration File Locations

There are **three separate `.env` files** in this project:

1. **Project root `.env`** - Template/reference (not used by Docker Compose)
2. **`frontend/.env`** - Used by `frontend/docker-compose.yml` ✅
3. **`backend/.env`** - Used by `backend/docker-compose.yml` ✅

**Docker Compose reads `.env` from the same directory** as the `docker-compose.yml` file. When changing configuration, update the appropriate service's `.env` file:
- Frontend/Image Server changes → `frontend/.env`
- Backend/Vista3D changes → `backend/.env`

### Critical Variables (Must Set)

**`frontend/.env` (for Traefik path-based proxy deployment):**
```bash
# Data directories (absolute paths required)
DICOM_FOLDER="/absolute/path/to/dicom"
OUTPUT_FOLDER="/absolute/path/to/output"

# Server URLs (use public HTTPS URLs with Traefik path prefixes)
IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"
EXTERNAL_IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"
VISTA3D_SERVER="http://vista3d-server-standalone:8000"
VISTA3D_IMAGE_SERVER_URL="http://vista3d-image-server-for-frontend:8888"
ROOT_PATH="/vista-images"
```

**`backend/.env`:**
```bash
# NVIDIA NGC credentials
NGC_API_KEY="nvapi-xxxxx"
NGC_ORG_ID="your_org_id"

# Data directory
OUTPUT_FOLDER="/absolute/path/to/output"

# Server URLs (backend uses localhost)
VISTA3D_SERVER="http://localhost:8000"
IMAGE_SERVER="http://localhost:8888"

# GPU Optimization (optional)
# TRT_INFERENCE=False  # Set to False for Blackwell/newer GPUs unsupported by TensorRT

# Corporate Proxy (optional - only if behind corporate proxy)
# HTTP_PROXY="http://proxy.company.com:8080"
# HTTPS_PROXY="http://proxy.company.com:8080"
# NO_PROXY="localhost,127.0.0.1,.company.com"
```

**Note**: TRT_INFERENCE and proxy settings are configured in `docker-compose.yml` environment section, not `.env` file. See "GPU Compatibility and TensorRT" and "Corporate Proxy Configuration" sections for details.

**Project root `.env` (reference/template):**
```bash
# Data directories (absolute paths required)
DICOM_FOLDER="/absolute/path/to/dicom"
OUTPUT_FOLDER="/absolute/path/to/output"

# NVIDIA NGC credentials (backend only)
NGC_API_KEY="nvapi-xxxxx"
NGC_ORG_ID="your_org_id"

# Server URLs (depends on deployment)
# For remote backend with SSH tunnel:
VISTA3D_SERVER="http://host.docker.internal:8000"  # Frontend to backend
VISTA3D_IMAGE_SERVER_URL="http://host.docker.internal:8888"  # Backend to image server
IMAGE_SERVER="http://localhost:8888"  # Frontend to image server

# For all-local deployment (no reverse proxy):
# VISTA3D_SERVER="http://vista3d-server:8000"
# VISTA3D_IMAGE_SERVER_URL="http://image-server:8888"
# IMAGE_SERVER="http://localhost:8888"
# ROOT_PATH=""  # Empty - no reverse proxy

# For Traefik path-based proxy deployment (moto.hst.rdlabs.hpecorp.net):
# VISTA3D_SERVER="http://localhost:8000"
# VISTA3D_IMAGE_SERVER_URL="http://localhost:8888"
# IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"
# EXTERNAL_IMAGE_SERVER="https://moto.hst.rdlabs.hpecorp.net/vista-images"
# ROOT_PATH="/vista-images"
```

### Streamlit Configuration

See `frontend/.streamlit/config.toml`. For the current Traefik deployment, `baseUrlPath = "/vista"` is set so Streamlit serves all assets and WebSocket connections under the `/vista` prefix.

### Docker-Specific Variables
- `DOCKER_CONTAINER=true` - Set by Docker containers automatically
- `host.docker.internal` - Mac Docker special hostname for host access
- `ROOT_PATH` - Base path for image server HTML links when behind path-based reverse proxy. Set to `/vista-images` for current Traefik deployment. Leave empty for direct or port-based deployments.

## Common Workflows

### Processing Medical Images

1. **Place DICOM files** in `dicom/{patient_id}/`
2. **Convert to NIfTI** (via Tools page or CLI):
   ```bash
   python3 frontend/utils/dicom2nifti.py --patient-id PA00000001
   ```
3. **Run segmentation** (via Tools page or CLI):
   ```bash
   python3 frontend/utils/segment.py --patient-id PA00000001 --scan-name scan.nii.gz
   ```
4. **View results** in NiiVue Viewer page

### Adding New Anatomical Structures

Edit `frontend/conf/vista3d_label_colors.json`:
```json
{
  "id": 128,
  "name": "New Structure",
  "color": [255, 0, 0],
  "description": "Description of structure"
}
```

### Debugging Connection Issues

**Test connectivity:**
```bash
cd frontend
bash quick_test.sh  # If available
```

**Manual tests:**
```bash
# Test Vista3D backend
curl http://localhost:8000/v1/health

# Test image server
curl http://localhost:8888/health

# From Vista3D container (critical for reverse tunnel)
docker exec vista3d-server-standalone curl http://localhost:8888/health
```

**SSH Tunnel Issues:**
- Ensure reverse tunnel uses `0.0.0.0`: `-R 8888:0.0.0.0:8888`
- Ubuntu SSH config may need `GatewayPorts clientspecified` in `/etc/ssh/sshd_config`
- Restart sshd: `sudo systemctl restart sshd`

## Testing

Currently no automated test suite. Manual testing via:
1. Tools page in web interface
2. Command-line utility scripts in `frontend/utils/`

## Kubernetes Deployment

Helm chart available in `helm/`:
```bash
cd helm
helm install vista3d . --namespace vista3d --create-namespace
```

See `helm/README.md` and `docs/HELM.md` for details.

## Important Notes

### Vista3D API Communication
- Vista3D requires image files accessible via HTTP URL
- Image server must be reachable from Vista3D container
- Use `VISTA3D_IMAGE_SERVER_URL` for backend-to-image-server communication
- Use `IMAGE_SERVER` for frontend-to-image-server communication

### Docker Volume Mounts
- Frontend container mounts: `output/`, `dicom/`, and source code (for hot reload)
- Image server mounts: `output/` and `dicom/` (read-only)
- Backend mounts: `output/` only

### File Size Filtering
- Segmentation utilities filter files < 0.1 MB by default (see `MIN_FILE_SIZE_MB` in `frontend/utils/constants.py`)
- Prevents processing of empty or corrupted NIfTI files

### NVIDIA NGC Requirements
- NGC API key required for backend only
- Frontend and image server do NOT need NGC access
- Get free API key at ngc.nvidia.com

### GPU Compatibility and TensorRT

**Blackwell GPU Support (sm_120 and newer architectures):**

Vista3D NIM 1.0.0 uses TensorRT for optimized inference, but TensorRT 10.x does not yet support Blackwell architecture GPUs (sm_120). If you have a newer GPU that's not supported by TensorRT, you'll see errors like:

```
Error Code 1: Internal Error (Unsupported SM: 0xc00)
Engine generation failed because all backend strategies failed
```

**Workaround**: Disable TensorRT optimization and run in pure PyTorch mode by adding to `backend/docker-compose.yml`:

```yaml
environment:
  - TRT_INFERENCE=False
```

This allows Vista3D to run on Blackwell and other newer GPUs without TensorRT acceleration. Performance will be slower than TensorRT-optimized inference but the model will function correctly.

**Note**: This workaround is temporary. Future Vista3D NIM versions with updated TensorRT support should work natively with Blackwell GPUs.

### Corporate Proxy Configuration

**For environments behind corporate proxies with SSL inspection (e.g., Zscaler):**

The Vista3D NIM container needs to download model files (~2-3GB) on first startup from NVIDIA NGC. If you're behind a corporate proxy with SSL inspection, add the following to `backend/docker-compose.yml`:

```yaml
environment:
  - HTTP_PROXY=http://proxy.company.com:8080
  - HTTPS_PROXY=http://proxy.company.com:8080
  - NO_PROXY=localhost,127.0.0.1,.company.com
  - SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.pem
  - REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-bundle.pem
  - CURL_CA_BUNDLE=/etc/ssl/certs/ca-bundle.pem
volumes:
  - /path/to/your/ca-bundle.pem:/etc/ssl/certs/ca-bundle.pem:ro
```

Replace `/path/to/your/ca-bundle.pem` with the path to your combined CA certificate bundle that includes both standard CAs and your corporate SSL inspection certificate (e.g., Zscaler root CA).

**Creating a combined CA bundle:**
```bash
cat /etc/ssl/certs/ca-certificates.crt /path/to/zscaler-root.crt > ~/.ca-bundle-combined.pem
```

## Common Issues

### "Connection refused" during segmentation
- Check SSH tunnel is running and uses `-R 8888:0.0.0.0:8888`
- Verify Vista3D container can access image server: `docker exec vista3d-server-standalone curl http://localhost:8888/health`

### "No patient folders found"
- Verify OUTPUT_FOLDER path is correct and absolute
- Check image server is running: `docker ps | grep image-server`
- Ensure folders exist: `ls -la $OUTPUT_FOLDER`

### Frontend can't connect to backend
- Verify backend is running: `curl http://localhost:8000/v1/health`
- Check SSH tunnel for remote backend
- Verify VISTA3D_SERVER in `frontend/.env` (NOT project root `.env`)

### Image Data opens localhost:8888 instead of public URL
- Check `IMAGE_SERVER` in `frontend/.env` should be `https://moto.hst.rdlabs.hpecorp.net/vista-images` (Docker Compose reads `.env` from same directory as docker-compose.yml)
- Verify environment variable is set: `docker exec vista3d-frontend-standalone printenv IMAGE_SERVER`
- Restart frontend after changing: `cd frontend && docker compose down && docker compose up -d`

### GPU not detected in backend
- Check NVIDIA drivers: `nvidia-smi`
- Verify NVIDIA Container Toolkit: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
- Check docker-compose.yml has GPU configuration

### TensorRT engine build failure / Unsupported GPU architecture
**Symptoms:**
- Container crashes during startup
- Error messages: `Unsupported SM: 0xc00` or `Engine generation failed`
- Log shows: `Error Code 1: Internal Error (Unsupported SM: ...)`

**Cause**: Newer GPU architecture (e.g., Blackwell sm_120) not supported by TensorRT 10.x

**Solution**: Add `TRT_INFERENCE=False` to `backend/docker-compose.yml` environment variables to disable TensorRT and use PyTorch mode. See "GPU Compatibility and TensorRT" section above for details.

### NGC model download failures
**Symptoms:**
- Container shows "Error downloading models"
- Connection timeout or authentication errors
- Error: `Connection timed out` to `authn.nvidia.com` or `xfiles.ngc.nvidia.com`

**Causes and Solutions:**

1. **Corporate proxy blocking NGC access**:
   - Add proxy environment variables to `backend/docker-compose.yml`
   - Mount corporate CA bundle for SSL inspection
   - See "Corporate Proxy Configuration" section above

2. **Invalid NGC credentials**:
   - Verify `NGC_API_KEY` and `NGC_ORG_ID` in `backend/.env`
   - Test credentials: `ngc config set` then `ngc registry model list`
   - Get new API key from ngc.nvidia.com if needed

3. **Firewall/network restrictions**:
   - Ensure outbound HTTPS access to `*.nvidia.com` and `*.ngc.nvidia.com`
   - Check if `curl https://authn.nvidia.com` works from server

**Alternative**: If NGC downloads keep failing, manually download model bundle using NGC CLI:
```bash
ngc registry model download-version nim/nvidia/vista3d:0.5.7 --dest ./nim-cache
```

### Port 8000 already in use
- **Portainer conflict**: If Portainer is using port 8000, reconfigure it:
  ```bash
  docker stop portainer && docker rm portainer
  docker run -d --name portainer --restart unless-stopped \
    -p 6443:9443 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v portainer_data:/data \
    portainer/portainer-ce:lts
  ```
- Check what's using port 8000: `docker ps -a | grep 8000`
- Vista3D requires port 8000 for the AI inference API

### Traefik proxy issues (path-based routing)
- **404 Not Found**: Verify routes exist in `/data/opt/Traefik/dynamic.yml` for `/vista` and `/vista-images`
- **Broken links in image server**: Ensure `ROOT_PATH=/vista-images` so HTML directory listing links include the prefix
- **WebSocket disconnects**: Traefik v3 handles WebSocket upgrades automatically; check Traefik logs if issues persist
- **Streamlit routing errors**: Ensure `baseUrlPath = "/vista"` is set in `frontend/.streamlit/config.toml`
- **Mixed content warnings**: Ensure `IMAGE_SERVER` uses HTTPS (e.g., `https://host/vista-images`)

## Additional Documentation

Comprehensive guides in `docs/`:
- `SETUP_GUIDE.md` - Detailed setup instructions
- `QUICK_START.md` - Quick start guide (3 steps)
- `DEPLOYMENT_GUIDE.md` - Deployment scenarios
- `SSH_TUNNEL_GUIDE.md` - SSH tunneling details
- `BACKEND_GUIDE.md` - Backend setup
- `HELM.md` - Kubernetes deployment
