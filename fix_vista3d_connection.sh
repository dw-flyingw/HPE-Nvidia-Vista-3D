#!/bin/bash

echo "🔧 Fixing Vista3D Connection Issue"
echo "=================================="

echo ""
echo "1. Checking current frontend container environment:"
if docker ps | grep -q vista3d-frontend-standalone; then
    echo "   ✅ Frontend container is running"
    echo "   Current VISTA3D_SERVER setting:"
    docker exec vista3d-frontend-standalone env | grep VISTA3D_SERVER || echo "   ❌ VISTA3D_SERVER not set"
else
    echo "   ❌ Frontend container not running"
fi

echo ""
echo "2. Checking if .env file exists and what it contains:"
if [ -f "frontend/.env" ]; then
    echo "   ✅ .env file exists"
    echo "   VISTA3D_SERVER setting in .env:"
    grep VISTA3D_SERVER frontend/.env || echo "   No VISTA3D_SERVER in .env"
else
    echo "   ✅ No .env file (will use docker-compose defaults)"
fi

echo ""
echo "3. Testing container-to-container communication:"
if docker ps | grep -q vista3d-frontend-standalone; then
    echo "   Testing vista3d-server:8000:"
    docker exec vista3d-frontend-standalone \
        curl -s http://vista3d-server:8000/v1/vista3d/info >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✅ vista3d-server:8000 works"
    else
        echo "   ❌ vista3d-server:8000 failed"
    fi
    
    echo "   Testing localhost:8000:"
    docker exec vista3d-frontend-standalone \
        curl -s http://localhost:8000/v1/vista3d/info >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✅ localhost:8000 works"
    else
        echo "   ❌ localhost:8000 failed"
    fi
fi

echo ""
echo "4. Recommended fix:"
echo "   Run these commands on your remote Linux server:"
echo ""
echo "   # Stop containers"
echo "   cd ~/path/to/frontend && docker-compose down"
echo "   cd ~/path/to/backend && docker-compose down"
echo ""
echo "   # Remove any .env file that might override defaults"
echo "   rm -f frontend/.env"
echo ""
echo "   # Start containers with fresh configuration"
echo "   cd ~/path/to/backend && docker-compose up -d"
echo "   sleep 10"
echo "   cd ~/path/to/frontend && docker-compose up -d"
echo "   sleep 30"
echo ""
echo "   # Verify the fix"
echo "   docker exec vista3d-frontend-standalone env | grep VISTA3D_SERVER"
echo "   # Should show: VISTA3D_SERVER=http://vista3d-server:8000"

echo ""
echo "5. Alternative: Create .env file with correct values"
echo "   Create frontend/.env with:"
echo "   VISTA3D_SERVER=http://vista3d-server:8000"
echo "   VISTA3D_IMAGE_SERVER_URL=http://image-server:8888"
echo "   IMAGE_SERVER=http://localhost:8888"
echo "   DICOM_FOLDER=/path/to/dicom"
echo "   OUTPUT_FOLDER=/path/to/output"
