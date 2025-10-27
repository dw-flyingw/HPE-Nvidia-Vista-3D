# HPE NVIDIA Vista3D Backend Setup

## Prerequisites

- Ubuntu Linux with NVIDIA GPU
- Docker with NVIDIA Container Toolkit installed
- NVIDIA NGC API key (get a free key at https://ngc.nvidia.com/)

## Setup Instructions

### 1. Run the Setup Script

From the `backend` directory, run the setup script:

```bash
python3 setup.py
```

The setup script will:

1. **Check System Requirements** - Verifies:
   - Linux OS
   - Docker installation
   - NVIDIA GPU detection
   - NVIDIA Container Toolkit functionality

2. **Configure NVIDIA NGC** - Prompts for your NGC API key
   
   When prompted, enter your NVIDIA NGC API key (it should start with `nvapi-`):
   ```
   Enter your NVIDIA NGC API key (starts with 'nvapi-'): nvapi-xxxxx
   ```
   
   You can get a free API key by:
   - Signing up at https://ngc.nvidia.com/
   - Logging into your account
   - Navigating to your profile settings
   - Generating an API key

3. **Create Data Directories** - Sets up the output folder structure

4. **Create Environment Configuration** - Generates a `.env` file with your NGC API key and configuration settings

5. **Pull Vista3D Docker Image** - Optionally pulls the Vista3D Docker image (large ~30GB download)

### 2. Start the Backend Server

After setup is complete, start the backend server:

```bash
docker compose up
```

**Note**: The backend does NOT start an image server. The image server is started by the frontend setup. The backend is configured to access the image server via the SSH tunnel.

### 3. Create SSH Tunnel (from your Mac)

If you're accessing the server from a Mac, create an SSH tunnel:

```bash
ssh -L 8000:localhost:8000 -R 8888:0.0.0.0:8888 user@server-address
```

This tunnel enables:
- Mac to access Vista3D at `localhost:8000`
- Vista3D to access your Mac's image server at `localhost:8888`

### 4. Access the API

- **From the server**: http://localhost:8000/docs
- **From your Mac** (via SSH tunnel): http://localhost:8000/docs

## Stopping the Server

To stop the backend server:

```bash
docker compose down
```

## Configuration

The setup script creates a `.env` file in the `backend` directory with the following configuration:

- `NGC_API_KEY` - Your NVIDIA NGC API key
- `OUTPUT_FOLDER` - Directory for processed output files
- `VISTA3D_SERVER` - Backend server URL
- `IMAGE_SERVER` - Image server URL
- `COMPOSE_PROJECT_NAME` - Docker Compose project name

## Troubleshooting

### If system requirements are not met

The script will warn you if system requirements are not met, but you can choose to continue anyway. Common issues:

- **Docker not found**: Install Docker
- **NVIDIA GPU not detected**: Verify GPU installation with `nvidia-smi`
- **NVIDIA Container Toolkit not working**: Reinstall the NVIDIA Container Toolkit

### If image pull fails

If the Vista3D Docker image fails to pull during setup, you can pull it later:

```bash
docker compose pull
```

### NGC API Key Issues

If your NGC API key doesn't start with `nvapi-`, make sure you've copied it correctly from your NGC account settings.

