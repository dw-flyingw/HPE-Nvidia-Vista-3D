# frontend/utils/server_status.py (Corrected)

import streamlit as st
import os
import requests
import urllib3

# Disable SSL warnings when using self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_image_server_status():
    """Check if the image server is available by requesting the health endpoint."""
    image_server_url = os.getenv("IMAGE_SERVER")

    if not image_server_url:
        return False

    try:
        # Use the /health endpoint which the FastAPI server provides
        health_url = f"{image_server_url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=5, verify=False)
        if response.status_code == 200:
            return True
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        pass
    
    # If localhost failed and we're in Docker, try the service name
    # Check if we're likely in Docker (you can enhance this check)
    if "localhost" in image_server_url or "127.0.0.1" in image_server_url:
        try:
            docker_url = image_server_url.replace("localhost", "image-server").replace("127.0.0.1", "image-server")
            health_url = f"{docker_url.rstrip('/')}/health"
            response = requests.get(health_url, timeout=5, verify=False)
            return response.status_code == 200
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            pass
    
    return False

def check_vista3d_server_status():
    """Check if the Vista3D server is available, now including the API key."""
    vista3d_server_url = os.getenv("VISTA3D_SERVER")
    api_key = os.getenv("VISTA3D_API_KEY") # ⬅️ ADDED: Read the API key from environment

    if not vista3d_server_url:
        return False

    try:
        # ADDED: Prepare headers for the request
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            print("DEBUG: Using API Key for Vista3D status check.")

        # Make the request with the new headers
        response = requests.get(f"{vista3d_server_url.rstrip('/')}/v1/vista3d/info", headers=headers, timeout=3, verify=False)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def render_server_status_sidebar():
    """Render server status message in sidebar."""
    if check_image_server_status():
        st.sidebar.success("""📥 **Image Server**
✅ Online""")
    else:
        st.sidebar.error("""📥 **Image Server**
❌ Offline""")

    if check_vista3d_server_status():
        st.sidebar.success("""🫁 **Vista3D Server**
✅ Online""")
    else:
        st.sidebar.error("""🫁 **Vista3D Server**
❌ Offline""")