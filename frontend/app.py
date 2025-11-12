import streamlit as st
from pathlib import Path
import sys
import requests
import os
from urllib.parse import urlparse
import subprocess
import json
import base64
import mimetypes
from typing import List, Dict, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import extra_streamlit_components as stx


# Add the application root to the Python path to ensure modules are found.
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Fallback if python-dotenv is not available
    pass

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent / 'utils'))
from utils.navigation import render_navigation
from assets.vista3d_badge import render_nvidia_vista_card as _render_nvidia_vista_card
from assets.hpe_badge import render_hpe_badge as _render_hpe_badge
#from assets.niivue_badge import render_niivue_badge as _render_niivue_badge

from utils.server_status import render_server_status_sidebar

def render_nvidia_vista_card():
    """Delegate rendering to assets.vista3d_badge module."""
    _render_nvidia_vista_card()
st.set_page_config(
    page_title="NIfTI Vessel Segmentation and Viewer",
    page_icon="🩻",
    layout="wide",
)

# Render navigation and get the navigation instance
nav = render_navigation()

# Main content based on current page
current_page = nav.get_current_page()

if current_page == 'home':
    # Render Nvidia Vista 3D card in sidebar
    render_nvidia_vista_card()
    # Render HPE AI badge in sidebar
    _render_hpe_badge()
    # Render NiiVue badge in sidebar
    #_render_niivue_badge()
    
    # Add spacing between HPE badge and server status widgets
    st.sidebar.markdown("")
    
    # Render server status widgets in sidebar
    render_server_status_sidebar()
    
    
    # Welcome message and navigation guidance
    st.markdown("""
    ## HPE-NVIDIA Medical Imaging Segmentation

    This platform provides automated vessel segmentation using NVIDIA's Vista3D model on HPE infrastructure, transforming DICOM medical imaging data into actionable clinical insights through AI-powered segmentation and 3D visualization.
    
    **🔄 Workflow Process**:  
    1. **📁 Add DICOM Folders**: Upload patient DICOM imaging data through the Image Data section
    2. **🔄 Convert to NIfTI**: Automatically convert DICOM files to NIfTI format for processing
    3. **🫁 AI Segmentation**: Run Vista3D model to perform automated vessel and organ segmentation
    4. **👁️ 3D Visualization**: View and analyze results using the interactive NiiVue viewer
    
    > **📋 Vista3D Capabilities & Limitations**:  
    > Vista3D supports both **CT and MRI DICOM files** (converted to NIfTI format) and excels at whole-body organ and lesion segmentation across 127+ anatomical structures. However, it has specific limitations: while it can process brain imaging data, it may not be optimal for detailed brain structure segmentation tasks that typically require specialized brain-focused models.
    
    Use the navigation menu on the left to access different features:
    
    - **📥 Image Data**: Browse and analyze patient medical imaging data
    - **🩻 NiiVue Viewer**: Interactive medical image viewer for NIfTI files
    - **🛠️ Tools**: Utilities for medical image processing
    """)
    

elif current_page == 'image_data':
    # Import and run Image Data content
    sys.path.append(str(Path(__file__).parent))
    from Image_Data import main as image_data_main
    image_data_main()

elif current_page == 'niivue':
    # Import and run NiiVue content
    sys.path.append(str(Path(__file__).parent))
    from NiiVue_Viewer import main as niivue_viewer_main
    niivue_viewer_main()

elif current_page == 'tools':
    # Import and run Tools content
    sys.path.append(str(Path(__file__).parent))
    from Tools import main as tools_main
    tools_main()
    

