# Quick Fix: Docker Compose on Ubuntu Server

## Your Issue
Frontend shows: `❌ Offline • http://host.docker.internal:8000`  
But the server IS reachable at: `http://localhost:8000/v1/health/live`

## Root Cause
`host.docker.internal` only works on Mac/Windows Docker Desktop.  
On Linux, containers cannot use this special DNS name.

## Quick Fix (Choose One)

### ✅ OPTION 1: Same Server (Best for Ubuntu deployment)

If backend and frontend are both running on the same Ubuntu machine:

**Step 1:** Create `.env` file in the `frontend` directory:
```bash
VISTA3D_SERVER="http://vista3d-server:8000"
VISTA3D_IMAGE_SERVER_URL="http://image-server:8888"
IMAGE_SERVER="http://localhost:8888"
EXTERNAL_IMAGE_SERVER="http://localhost:8888"
DICOM_FOLDER="/path/to/your/dicom"
OUTPUT_FOLDER="/path/to/your/output"
```

**Step 2:** Start containers (from frontend directory):
```bash
docker-compose up -d
```

**Why it works:** Containers on the same Docker network can resolve each other by name.

---

### ✅ OPTION 2: Different Servers

If backend and frontend are on different Ubuntu machines:

**Step 1:** Find the backend server's IP:
```bash
# On Ubuntu backend machine
hostname -I
# Example output: 192.168.1.100
```

**Step 2:** Create `.env` in frontend directory:
```bash
VISTA3D_SERVER="http://192.168.1.100:8000"
VISTA3D_IMAGE_SERVER_URL="http://192.168.1.100:8888"
```

**Step 3:** Allow firewall ports on backend:
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8888/tcp
sudo ufw enable
```

**Step 4:** Start frontend:
```bash
docker-compose up -d
```

---

### ✅ OPTION 3: Mac → Ubuntu Remote Setup

If you're coding on Mac and running containers on Ubuntu:

**On Mac:**
```bash
# Establish SSH tunnels to Ubuntu server
ssh -L 8000:localhost:8000 \
    -R 8888:localhost:8888 \
    user@ubuntu-server-ip
```

**On Mac (.env file):**
```bash
VISTA3D_SERVER="http://host.docker.internal:8000"
VISTA3D_IMAGE_SERVER_URL="http://host.docker.internal:8888"
```

Keep the SSH command running in background while developing.

---

## Verify It Works

### Check container communication:
```bash
# Test from frontend container
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info
```

### Check sidebar status:
Open frontend at `http://localhost:8501`  
Sidebar should show: `✅ Online • http://vista3d-server:8000`

---

## What Changed in the Codebase

✅ Updated `frontend/docker-compose.yml`:
- Added explicit `vista3d-network` for container communication
- Image server now on same network

✅ Updated `backend/docker-compose.yml`:
- Added `extra_hosts: host-gateway` mapping (for Linux compatibility)
- Added explicit network configuration

✅ Updated `utils/server_status.py`:
- Already has fallback logic to try multiple URLs
- Will try container name even if configured URL fails

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Still shows "❌ Offline" | Rebuild containers: `docker-compose up -d --force-recreate` |
| Port 8000 already in use | Kill process: `sudo lsof -i :8000` or use different port |
| Containers can't reach each other | Check network: `docker network inspect vista3d_vista3d-network` |
| Firewall blocks connection | Run: `sudo ufw allow 8000/tcp` |

---

## Files Modified

- `frontend/docker-compose.yml` - Added networking
- `backend/docker-compose.yml` - Added Linux-compatible host mapping
- `dot_env_template` - Added Linux deployment notes
- `docs/LINUX_DEPLOYMENT.md` - Full documentation
- `.env.linux-example` - Environment template for Linux

See `docs/LINUX_DEPLOYMENT.md` for complete documentation.
