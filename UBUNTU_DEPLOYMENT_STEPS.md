# Ubuntu Server Deployment Steps

## ✅ What's Been Fixed

Your `.env` file has been updated with:
```
VISTA3D_SERVER=http://vista3d-server:8000
IMAGE_SERVER=http://localhost:8888
VISTA3D_IMAGE_SERVER_URL=http://image-server:8888
```

The `docker-compose.yml` files now include proper Docker networking.

## 🚀 Steps to Deploy on Ubuntu Server

### On Your Ubuntu Server (not local Mac):

#### 1. Copy the Updated Files

If you haven't already, sync these updated files to your Ubuntu server:
- `frontend/docker-compose.yml` ✅ (has vista3d-network)
- `frontend/.env` ✅ (updated with container names)
- `backend/docker-compose.yml` ✅ (has networking config)

#### 2. Stop Old Containers

```bash
cd ~/path/to/frontend
docker-compose down

cd ~/path/to/backend
docker-compose down
```

#### 3. Remove Old Containers (force cleanup)

```bash
docker container rm vista3d-frontend-standalone vista3d-image-server-for-frontend vista3d-server-standalone -f 2>/dev/null
docker network rm vista3d_vista3d-network -f 2>/dev/null
```

#### 4. Start Backend First

```bash
cd ~/path/to/backend
docker-compose up -d

# Wait a few seconds for it to fully start
sleep 5

# Verify Vista3D is ready
curl -v http://localhost:8000/v1/vista3d/info
```

#### 5. Start Frontend

```bash
cd ~/path/to/frontend
docker-compose up -d

# Wait for it to start (30-60 seconds for first startup)
sleep 30

# Check logs
docker-compose logs vista3d-frontend
```

#### 6. Test Internal Communication

```bash
# Test from frontend container to backend container via network
docker exec vista3d-frontend-standalone \
  curl -v http://vista3d-server:8000/v1/vista3d/info

# Expected: HTTP 200 response ✅
```

#### 7. Access Frontend

Open your browser:
```
http://localhost:8501
```

The sidebar should show:
```
✅ Vista3D Server
✅ Online • http://vista3d-server:8000
```

## If Still Showing Offline

### Check what the container sees:

```bash
# Inside frontend container, test the URLs it tries:
docker exec vista3d-frontend-standalone bash << 'INNER_EOF'
echo "=== Testing container name ==="
curl -v http://vista3d-server:8000/v1/vista3d/info 2>&1 | head -20

echo -e "\n=== Testing localhost ==="
curl -v http://localhost:8000/v1/vista3d/info 2>&1 | head -20

echo -e "\n=== Testing 127.0.0.1 ==="
curl -v http://127.0.0.1:8000/v1/vista3d/info 2>&1 | head -20
INNER_EOF
```

### Check Docker network:

```bash
# Verify network exists
docker network ls | grep vista3d

# Inspect network
docker network inspect vista3d_vista3d-network

# Check if containers are on network
docker inspect vista3d-frontend-standalone | grep -A 20 "Networks"
```

### Check environment variables:

```bash
# Verify correct env vars
docker exec vista3d-frontend-standalone env | grep -E "VISTA3D|IMAGE_SERVER"
```

### Check frontend logs:

```bash
docker-compose -f frontend/docker-compose.yml logs -f vista3d-frontend
```

## Verification Checklist

- [ ] Stopped old containers with `docker-compose down`
- [ ] .env updated with container names
- [ ] Backend started and health check passing
- [ ] Frontend started successfully
- [ ] Frontend can reach backend via container name
- [ ] Sidebar shows ✅ Online status
