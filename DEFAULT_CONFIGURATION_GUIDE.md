# ✅ Smart Default Configuration - Now "Just Works"

## What Changed

The docker-compose files now use intelligent defaults that work **automatically** on both Mac Docker Desktop and Linux without manual `.env` configuration.

### Before (Old Way - Broken on Linux)
```
VISTA3D_SERVER=${VISTA3D_SERVER:-http://host.docker.internal:8000}  # ❌ Linux fails
```

### After (New Way - Works Everywhere)
```
VISTA3D_SERVER=${VISTA3D_SERVER:-http://vista3d-server:8000}  # ✅ Mac & Linux work
```

## How It Works

### Smart Defaults (No Configuration Needed)

**On Mac Docker Desktop:**
- Container names resolve via Docker Desktop's DNS
- `http://vista3d-server:8000` → Works automatically ✅

**On Linux (Ubuntu):**
- Container names resolve via Docker bridge network
- `http://vista3d-server:8000` → Works automatically ✅

### Fallback Logic (In Code)

Even if the container name fails, the frontend tries:
1. `http://vista3d-server:8000` (container name)
2. `http://localhost:8000` (same host)
3. `http://127.0.0.1:8000` (localhost IP)

**Result:** System automatically finds the backend no matter how it's deployed!

## Quick Start - Nothing to Configure!

### On Ubuntu Server:

```bash
# 1. Start backend
cd ~/path/to/backend
docker-compose up -d

# 2. Start frontend  
cd ~/path/to/frontend
docker-compose up -d

# 3. Open browser
# http://localhost:8501
# Sidebar should show: ✅ Online
```

That's it! No manual URL configuration needed.

## Why This Works Better

| Scenario | Old (host.docker.internal) | New (vista3d-server) |
|----------|---------------------------|---------------------|
| Mac Docker Desktop | ✅ Works | ✅ Works |
| Linux Ubuntu | ❌ Fails | ✅ Works |
| Different host | ❌ Fails | ✅ Falls back to localhost or IP |
| SSH tunnel | ✅ Works | ✅ Works (can override .env) |

## Configuration Still Optional

Required only:
```bash
DICOM_FOLDER="/path/to/dicom"
OUTPUT_FOLDER="/path/to/output"
NGC_API_KEY="nvapi-xxx"
```

Everything else has smart defaults that work automatically!
