# Remote Linux Server - Container Setup

## ✅ Problem Identified and Fixed

**Issue**: Vista3D container and Frontend container were on different Docker networks
- Vista3D container: `default` network  
- Frontend container: `vista3d-network` network
- Result: Containers couldn't reach each other by name

**Fix**: Updated backend/docker-compose.yml to use `vista3d-network` (same as frontend)

## 🚀 Deployment Steps (on your remote Linux server)

### 1. Stop all containers
```bash
# Stop frontend
cd ~/path/to/frontend
docker-compose down

# Stop backend  
cd ~/path/to/backend
docker-compose down
```

### 2. Clean up networks (optional but recommended)
```bash
# Remove old networks
docker network rm vista3d_vista3d-network 2>/dev/null || true
docker network rm vista3d_default 2>/dev/null || true
```

### 3. Start backend first
```bash
cd ~/path/to/backend
docker-compose up -d

# Wait for Vista3D to fully start
sleep 10

# Verify Vista3D is running
curl http://localhost:8000/v1/vista3d/info
```

### 4. Start frontend
```bash
cd ~/path/to/frontend
docker-compose up -d

# Wait for frontend to start
sleep 30
```

### 5. Test container-to-container communication
```bash
# Test if frontend can reach Vista3D via container name
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info

# Expected: HTTP 200 response ✅
```

### 6. Verify from your Mac (via SSH tunnel)
```bash
# Test Vista3D
curl http://localhost:8000/v1/vista3d/info

# Test frontend
curl http://localhost:8501

# Open in browser
# http://localhost:8501
# Sidebar should show: ✅ Online • http://vista3d-server:8000
```

## 🔍 Troubleshooting

### Check if containers are on same network:
```bash
# List networks
docker network ls | grep vista3d

# Inspect the network
docker network inspect vista3d_vista3d-network

# Check container network assignments
docker inspect vista3d-server-standalone | grep -A 10 "Networks"
docker inspect vista3d-frontend-standalone | grep -A 10 "Networks"
```

### Check container logs:
```bash
# Frontend logs
docker-compose -f frontend/docker-compose.yml logs vista3d-frontend

# Backend logs  
docker-compose -f backend/docker-compose.yml logs vista3d-server
```

### Test DNS resolution:
```bash
# From frontend container, test DNS
docker exec vista3d-frontend-standalone nslookup vista3d-server
docker exec vista3d-frontend-standalone ping -c 1 vista3d-server
```

## ✅ Expected Result

- Frontend sidebar shows: `✅ Online • http://vista3d-server:8000`
- No more "❌ Offline" errors
- Containers can communicate via container names
- SSH port forwarding works from your Mac

## 📋 Configuration Summary

**Frontend** (frontend/docker-compose.yml):
- Network: `vista3d-network`
- VISTA3D_SERVER: `http://vista3d-server:8000` ✅

**Backend** (backend/docker-compose.yml):  
- Network: `vista3d-network` ✅ (updated)
- Container name: `vista3d-server-standalone`
- Port: `8000:8000`

Both containers now on same network = communication works! 🎉
