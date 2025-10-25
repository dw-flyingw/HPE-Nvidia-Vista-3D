# Linux Deployment Guide: Fixing `host.docker.internal` Issues

## Problem Summary

When running Docker Compose on a **Linux server** (Ubuntu, etc.), the frontend shows:
```
🫁 Vista3D Server
❌ Offline • http://host.docker.internal:8000
```

Even though the Vista3D server IS accessible at `http://localhost:8000/v1/health/live` on the host.

### Root Cause

`host.docker.internal` is a **Mac/Windows Docker Desktop-only feature**. It doesn't exist on Linux. Linux Docker containers cannot use this special DNS name to reach the host machine.

## Solutions

### Solution 1: Same Host Deployment (Recommended)

If both frontend and backend are running on the **same Ubuntu server**, use the Docker container network name:

#### Step 1: Update `.env` for Linux

```bash
# .env file for Linux deployment
VISTA3D_SERVER="http://vista3d-server:8000"
VISTA3D_IMAGE_SERVER_URL="http://image-server:8888"
```

#### Step 2: Run Docker Compose

The frontend's `docker-compose.yml` now includes proper networking:

```bash
cd /path/to/frontend
docker-compose up -d
```

The frontend will resolve `vista3d-server` via the internal Docker network.

### Solution 2: Different Hosts Deployment

If the backend Vista3D server is on a **different Ubuntu machine**, you need to:

#### Step 1: Get the Backend Host IP

```bash
# On the backend Ubuntu machine
hostname -I
# Example output: 192.168.1.100
```

#### Step 2: Update `.env` for Frontend

```bash
# .env file for frontend (on different host)
VISTA3D_SERVER="http://192.168.1.100:8000"
# If Docker port mapping is different:
VISTA3D_SERVER="http://backend-server.example.com:8000"
```

#### Step 3: Ensure Firewall Rules

```bash
# On the backend Ubuntu machine, allow port 8000
sudo ufw allow 8000/tcp
sudo ufw enable
```

### Solution 3: SSH Tunneling (For Secure Remote Access)

If you're developing from a Mac/local machine and want to reach a remote Ubuntu server:

#### On your Mac (local machine):

```bash
# Establish SSH tunnels to Ubuntu backend
ssh -L 8000:localhost:8000 \
    -R 8888:localhost:8888 \
    user@ubuntu-server-ip

# What this does:
# -L 8000:localhost:8000 → You can access backend at http://localhost:8000
# -R 8888:localhost:8888 → Backend can reach your Mac's image server
```

#### Update `.env` (on your Mac):

```bash
# For local Docker Desktop
VISTA3D_SERVER="http://host.docker.internal:8000"

# For the SSH tunnel above:
# - Your Mac's Docker can reach http://host.docker.internal:8000 (forwarded to Ubuntu:8000)
# - Backend's http://host.docker.internal:8888 (reverse tunnel to Mac:8888)
```

## How the Frontend Connection Works (Linux)

The `check_vista3d_server_status()` function in `utils/server_status.py` tries URLs in this order:

1. **Configured URL** - `http://host.docker.internal:8000` (fails on Linux)
2. **Container name** - `http://vista3d-server:8000` ✅ (works if on same network)
3. **Localhost** - `http://localhost:8000` (depends on Docker network mode)
4. **IP address** - `http://127.0.0.1:8000` (last resort)

### Fallback Behavior

Even if the configured URL fails, the frontend continues trying alternatives. This means:
- The health check may take longer (tries 3-4 URLs)
- Eventually it may show "❌ Offline" if NONE of the URLs work
- The actual requests might still succeed via a fallback URL

## Docker Networking Configuration

Both compose files now include explicit networks:

**Frontend** (`frontend/docker-compose.yml`):
```yaml
networks:
  vista3d-network:
    driver: bridge
```

**Backend** (`backend/docker-compose.yml`):
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"  # Maps to gateway IP on Linux
networks:
  default:
    driver: bridge
```

## Troubleshooting

### Check if containers can communicate:

```bash
# Inside frontend container
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info

# Inside image-server container  
docker exec vista3d-image-server-for-frontend \
  curl -v http://localhost:8888
```

### Check Docker networks:

```bash
# List networks
docker network ls

# Inspect network
docker network inspect vista3d_vista3d-network

# Check container IP
docker inspect vista3d-frontend-standalone | grep '"IPAddress"'
```

### Check host connectivity:

```bash
# On Ubuntu backend, test from host
curl -v http://localhost:8000/v1/vista3d/info

# Test from frontend container
docker exec vista3d-frontend-standalone \
  curl -v http://192.168.1.X:8000/v1/vista3d/info  # Replace with actual IP
```

## Performance Optimization

On Linux, Docker uses the bridge network driver which is efficient for container-to-container communication. The container name resolution is fast and reliable.

### For maximum performance:
1. Run both frontend and backend on the **same Ubuntu host** (Solution 1)
2. Use container names instead of IP addresses
3. Avoid SSH tunnels unless necessary (they add latency)

## Common Issues and Fixes

| Issue | Cause | Solution |
|-------|-------|----------|
| Container name not resolving | Containers not on same network | Add network section to docker-compose |
| `host.docker.internal` not working | Running on Linux | Use container name or external IP |
| Firewall blocking | UFW/iptables rules | `sudo ufw allow 8000/tcp` |
| DNS resolution timeout | Network not properly configured | Rebuild containers: `docker-compose up -d --force-recreate` |
| Port already in use | Port conflict | Change port in compose file or check `sudo lsof -i :8000` |

## References

- [Docker networking on Linux](https://docs.docker.com/engine/network/)
- [host.docker.internal availability](https://docs.docker.com/desktop/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host)
- [Docker Compose networking](https://docs.docker.com/compose/networking/)
