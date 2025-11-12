#!/bin/bash
# Stops the background port-forwarding process started by setup_and_redeploy.sh

set -e

PID_FILE=".port_forward.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "Stopping port-forward process with PID: $PID"
    kill "$PID" >/dev/null 2>&1 || true
    rm "$PID_FILE"
    echo "Port-forwarding stopped."
else
    echo "No running port-forward process found (no PID file)."
fi
