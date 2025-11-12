#!/bin/bash
set -e

echo "Attempting to fix Docker daemon DNS configuration..."

DAEMON_JSON="/etc/docker/daemon.json"

# Check if daemon.json exists, if not, create it
if [ ! -f "$DAEMON_JSON" ]; then
    echo "{}" | sudo tee "$DAEMON_JSON" > /dev/null
    echo "Created empty $DAEMON_JSON"
fi

# Use jq to add/update the dns entry, preserving other entries
# If jq is not installed, install it
if ! command -v jq &> /dev/null
then
    echo "jq not found, installing..."
    sudo apt-get update
    sudo apt-get install -y jq
fi

# Read the current daemon.json, add/update dns, and write back
sudo jq '.dns = ["8.8.8.8", "8.8.4.4"]' "$DAEMON_JSON" | sudo tee "$DAEMON_JSON" > /dev/null
echo "Updated $DAEMON_JSON with DNS servers 8.8.8.8 and 8.8.4.4"

echo "Restarting Docker daemon for changes to take effect..."
sudo systemctl restart docker
echo "Docker daemon restarted."

echo "Docker DNS configuration fix applied. Please try building your Docker images again."
