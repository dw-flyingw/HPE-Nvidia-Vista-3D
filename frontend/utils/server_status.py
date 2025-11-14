# frontend/utils/server_status.py (Corrected)

import streamlit as st
import os
import requests

def check_image_server_status():
    """Check if the image server is available by requesting the root URL."""
    image_server_url = os.getenv("IMAGE_SERVER")

    if not image_server_url:
        return False

    try:
        # CHANGED: The simple python http.server doesn't have a /health endpoint.
        # We will check the root URL ('/') instead, which should return a 200 OK
        # with a directory listing if the server is running.
        response = requests.get(image_server_url.rstrip('/'), timeout=2)
        # A 404 is also acceptable if the root directory is empty, but we'll stick to 200 for a positive check.
        return response.status_code == 200
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
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
        response = requests.get(f"{vista3d_server_url.rstrip('/')}/v1/vista3d/info", headers=headers, timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def render_server_status_sidebar():
    """Render server status message in sidebar."""
    # This part remains the same, it just calls the corrected functions above.
    image_server_url = os.getenv("IMAGE_SERVER", "Not Configured")
    if check_image_server_status():
        st.sidebar.success(f"""📥 **Image Server**  
✅ Online • {image_server_url}""")
    else:
        st.sidebar.error(f"""📥 **Image Server**  
❌ Offline • {image_server_url}""")

    vista3d_server_url = os.getenv("VISTA3D_SERVER", "Not Configured")
    if check_vista3d_server_status():
        st.sidebar.success(f"""🫁 **Vista3D Server**  
✅ Online • {vista3d_server_url}""")
    else:
        st.sidebar.error(f"""🫁 **Vista3D Server**  
❌ Offline • {vista3d_server_url}""")