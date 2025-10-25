# Default Setup: Remote Linux Server with Containerized Services

## 🎯 Default Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Remote Linux Server                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Vista3D Server  │  │ Frontend        │  │ Image Server│ │
│  │ Container       │  │ Container       │  │ Container   │ │
│  │ Port 8000       │  │ Port 8501       │  │ Port 8888   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│           │                   │                   │         │
│           └───────────────────┼───────────────────┘         │
│                               │                             │
│                    vista3d-network                         │
└─────────────────────────────────────────────────────────────┘
                               │
                    SSH Port Forwarding
                               │
┌─────────────────────────────────────────────────────────────┐
│                        Your Mac                            │
│  http://localhost:8000  ←→  Vista3D Server                 │
│  http://localhost:8501  ←→  Frontend                       │
│  http://localhost:8888  ←→  Image Server                   │
└─────────────────────────────────────────────────────────────┘
```

## ✅ Configuration (Already Set Up)

### Frontend (frontend/docker-compose.yml)
```yaml
services:
  vista3d-frontend:
    container_name: vista3d-frontend-standalone
    ports: ["8501:8501"]
    environment:
      - VISTA3D_SERVER=http://vista3d-server:8000  # Container name
      - VISTA3D_IMAGE_SERVER_URL=http://image-server:8888
    networks: [vista3d-network]

  image-server:
    container_name: vista3d-image-server-for-frontend
    ports: ["8888:8888"]
    networks: [vista3d-network]

networks:
  vista3d-network:
    driver: bridge
```

### Backend (backend/docker-compose.yml)
```yaml
services:
  vista3d-server:
    container_name: vista3d-server-standalone
    ports: ["8000:8000"]
    networks: [vista3d-network]

networks:
  vista3d-network:
    driver: bridge
```

## 🚀 Quick Start (Remote Linux Server)

### 1. Prerequisites
```bash
# Ensure you have NGC credentials
export NGC_API_KEY="nvapi-your-key-here"
export NGC_ORG_ID="your-org-id"

# Or create backend/.env file:
echo "NGC_API_KEY=nvapi-your-key-here" > backend/.env
echo "NGC_ORG_ID=your-org-id" >> backend/.env
```

### 2. Start Backend
```bash
cd ~/path/to/backend
docker-compose up -d

# Wait for Vista3D to start (30-60 seconds)
sleep 30

# Verify it's running
curl http://localhost:8000/v1/vista3d/info
```

### 3. Start Frontend
```bash
cd ~/path/to/frontend
docker-compose up -d

# Wait for frontend to start
sleep 30

# Verify container communication
docker exec vista3d-frontend-standalone \
  curl http://vista3d-server:8000/v1/vista3d/info
```

### 4. SSH Port Forwarding (Your Mac)
```bash
# On your Mac, establish SSH tunnels
ssh -L 8000:localhost:8000 \
    -L 8501:localhost:8501 \
    -L 8888:localhost:8888 \
    user@remote-linux-server

# Keep this SSH session running
```

### 5. Access from Mac
- **Frontend**: http://localhost:8501
- **Vista3D API**: http://localhost:8000/v1/vista3d/info
- **Image Server**: http://localhost:8888

## 🔍 Verification

### Check Container Status
```bash
# On remote server
docker ps | grep -E "(vista3d|frontend)"

# Should show:
# vista3d-server-standalone
# vista3d-frontend-standalone  
# vista3d-image-server-for-frontend
```

### Check Network Connectivity
```bash
# Test container-to-container communication
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info

# Expected: HTTP 200 response
```

### Check from Mac (via SSH tunnel)
```bash
# Test Vista3D
curl http://localhost:8000/v1/vista3d/info

# Test frontend
curl http://localhost:8501

# Open browser
open http://localhost:8501
```

## 🎯 Expected Result

- **Frontend sidebar shows**: `✅ Online • http://vista3d-server:8000`
- **No "❌ Offline" errors**
- **All services accessible from Mac via SSH tunnel**
- **Containers communicate via Docker network**

## 🔧 Troubleshooting

### Containers can't reach each other
```bash
# Check if containers are on same network
docker network inspect vista3d_vista3d-network

# Should show both containers in "Containers" section
```

### Vista3D not starting
```bash
# Check logs
docker-compose -f backend/docker-compose.yml logs vista3d-server

# Check GPU availability
nvidia-smi
```

### SSH tunnel issues
```bash
# Test individual ports
telnet localhost 8000
telnet localhost 8501
telnet localhost 8888

# Restart SSH tunnel if needed
```

## 📋 Summary

This default setup provides:
- ✅ **Containerized services** on remote Linux server
- ✅ **Docker networking** for container communication
- ✅ **SSH port forwarding** for Mac access
- ✅ **No manual configuration** needed
- ✅ **Scalable and maintainable** architecture

Just run `docker-compose up -d` in both directories and establish SSH tunnels!
