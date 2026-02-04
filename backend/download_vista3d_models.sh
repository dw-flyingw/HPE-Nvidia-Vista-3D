#!/bin/bash
# Script to download Vista3D models in resumable chunks

set -e

CACHE_DIR="./nim-cache"
DOWNLOAD_DIR="${CACHE_DIR}/.download"
CHUNK_SIZE="50M"  # Download 50MB at a time

mkdir -p "$DOWNLOAD_DIR"

echo "Starting Vista3D container to capture download URLs..."
docker compose up -d

# Monitor logs and extract download URLs
echo "Monitoring logs for download URLs (this may take a minute)..."
timeout 120 docker logs -f vista3d-server-standalone 2>&1 | while read line; do
    # Extract URLs from error messages
    if echo "$line" | grep -q "https://xfiles.ngc.nvidia.com"; then
        URL=$(echo "$line" | grep -oP 'https://xfiles\.ngc\.nvidia\.com[^"]+' | head -1)
        if [ -n "$URL" ]; then
            echo "Found download URL!"
            echo "$URL" >> "$DOWNLOAD_DIR/urls.txt"
        fi
    fi
done || true

if [ ! -f "$DOWNLOAD_DIR/urls.txt" ]; then
    echo "No download URLs captured. Let me try alternative method..."
    echo "Checking NGC catalog..."

    # Alternative: Use NGC CLI to download the model package
    export NGC_HOME="$CACHE_DIR"

    # Try to download using NGC CLI directly
    echo "Attempting to download Vista3D model files using NGC CLI..."
    ngc registry model download-version nim/nvidia/vista3d:0.5.7 \
        --dest "$CACHE_DIR" \
        || echo "NGC CLI download failed, manual download needed"
fi

echo "Download script complete. Check $DOWNLOAD_DIR for progress."
