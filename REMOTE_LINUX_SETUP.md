# Remote Linux Server Setup with SSH Port Forwarding

## Your Current Setup

- **Remote Linux Server**: Running Vista3D server + Frontend container + Image server
- **Your Mac**: SSH port forwarding (8000, 8501, 8888)
- **Access**: http://localhost:8501 on your Mac → forwarded to remote server

## The Issue

Frontend container on remote server needs to reach Vista3D server, but the connection method depends on how Vista3D is running.

## Solution Options

### Option 1: Vista3D Server in Docker Container (Recommended)

If Vista3D is running in a Docker container on the remote server:

```bash
# On remote Linux server
cd ~/path/to/backend
docker-compose up -d

cd ~/path/to/frontend  
docker-compose up -d
```

**Configuration**: Uses container names (already set in docker-compose.yml)
- `VISTA3D_SERVER=http://vista3d-server:8000` ✅
- `VISTA3D_IMAGE_SERVER_URL=http://image-server:8888` ✅

### Option 2: Vista3D Server on Host (Not Containerized)

If Vista3D is running directly on the Linux host:

**Create .env file in frontend directory:**
```bash
# frontend/.env
VISTA3D_SERVER=http://host.docker.internal:8000
VISTA3D_IMAGE_SERVER_URL=http://host.docker.internal:8888
IMAGE_SERVER=http://localhost:8888
DICOM_FOLDER=/path/to/dicom
OUTPUT_FOLDER=/path/to/output
```

**Update backend/docker-compose.yml to add:**
```yaml
services:
  vista3d-server:
    # ... existing config ...
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Option 3: Vista3D Server on Different Host

If Vista3D is on a completely different server:

**Create .env file in frontend directory:**
```bash
# frontend/.env
VISTA3D_SERVER=http://192.168.1.100:8000  # Replace with actual Vista3D server IP
VISTA3D_IMAGE_SERVER_URL=http://192.168.1.100:8888
IMAGE_SERVER=http://localhost:8888
DICOM_FOLDER=/path/to/dicom
OUTPUT_FOLDER=/path/to/output
```

## Quick Diagnosis

Run this on your remote Linux server to check how Vista3D is running:

```bash
# Check if Vista3D is in a container
docker ps | grep vista3d

# Check if Vista3D is on host
curl -s http://localhost:8000/v1/vista3d/info | head -5

# Check what the frontend container sees
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info 2>&1 | head -10
```

## SSH Port Forwarding (Your Mac)

Your current setup should be:
```bash
# On your Mac
ssh -L 8000:localhost:8000 \
    -L 8501:localhost:8501 \
    -L 8888:localhost:8888 \
    user@remote-linux-server
```

Then access:
- Frontend: http://localhost:8501
- Vista3D: http://localhost:8000  
- Image Server: http://localhost:8888

## Testing the Fix

1. **Check Vista3D is accessible from remote server:**
   ```bash
   curl http://localhost:8000/v1/vista3d/info
   ```

2. **Check frontend container can reach Vista3D:**
   ```bash
   docker exec vista3d-frontend-standalone \
     curl http://vista3d-server:8000/v1/vista3d/info
   ```

3. **Check from your Mac (via SSH tunnel):**
   ```bash
   curl http://localhost:8000/v1/vista3d/info
   ```

4. **Open frontend on Mac:**
   http://localhost:8501
   Should show: ✅ Online

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Vista3D not in container | Use Option 2 (host.docker.internal) |
| Vista3D on different server | Use Option 3 (server IP) |
| SSH tunnel not working | Check SSH command, restart tunnel |
| Firewall blocking | `sudo ufw allow 8000/tcp` |
| Container can't reach host | Add extra_hosts to docker-compose |

