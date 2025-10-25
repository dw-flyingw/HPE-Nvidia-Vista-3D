#!/bin/bash

echo "🔍 Diagnosing Remote Linux Server Setup"
echo "========================================"

echo ""
echo "1. Checking if Vista3D is running in Docker container:"
docker ps | grep -i vista3d || echo "   ❌ No Vista3D container found"

echo ""
echo "2. Checking if Vista3D is running on host:"
curl -s http://localhost:8000/v1/vista3d/info >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Vista3D responding on localhost:8000"
    echo "   📋 This means Vista3D is running on the HOST (not containerized)"
else
    echo "   ❌ Vista3D not responding on localhost:8000"
fi

echo ""
echo "3. Checking frontend container status:"
docker ps | grep -i frontend || echo "   ❌ No frontend container found"

echo ""
echo "4. Testing frontend container → Vista3D connection:"
if docker ps | grep -q frontend; then
    echo "   Testing container name resolution:"
    docker exec vista3d-frontend-standalone \
        curl -s http://vista3d-server:8000/v1/vista3d/info >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✅ Frontend can reach Vista3D via container name"
    else
        echo "   ❌ Frontend cannot reach Vista3D via container name"
    fi
    
    echo "   Testing localhost resolution:"
    docker exec vista3d-frontend-standalone \
        curl -s http://localhost:8000/v1/vista3d/info >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✅ Frontend can reach Vista3D via localhost"
    else
        echo "   ❌ Frontend cannot reach Vista3D via localhost"
    fi
else
    echo "   ⚠️  Frontend container not running - start it first"
fi

echo ""
echo "5. Recommended solution based on findings:"
if docker ps | grep -q vista3d; then
    echo "   🐳 Vista3D is containerized → Use container names (current default)"
    echo "   ✅ Current config should work: VISTA3D_SERVER=http://vista3d-server:8000"
elif curl -s http://localhost:8000/v1/vista3d/info >/dev/null 2>&1; then
    echo "   🖥️  Vista3D is on host → Use host.docker.internal"
    echo "   🔧 Create frontend/.env with:"
    echo "      VISTA3D_SERVER=http://host.docker.internal:8000"
    echo "      VISTA3D_IMAGE_SERVER_URL=http://host.docker.internal:8888"
else
    echo "   ❓ Vista3D not found - check if it's running"
fi

echo ""
echo "6. Next steps:"
echo "   - Run this script on your remote Linux server"
echo "   - Follow the recommended solution above"
echo "   - Restart frontend container: docker-compose down && docker-compose up -d"
