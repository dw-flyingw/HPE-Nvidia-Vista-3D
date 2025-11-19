"""
Constants for the Vista3D application.
Centralized location for all magic strings, numbers, and configuration values.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PROJECT_ROOT is no longer needed - all paths should be full paths from .env

# File extensions
NIFTI_EXTENSIONS = ('.nii', '.nii.gz')
DICOM_EXTENSIONS = ('.dcm',)
IMAGE_EXTENSIONS = NIFTI_EXTENSIONS + DICOM_EXTENSIONS

# Directory structure - get from environment variables
OUTPUT_FOLDER_ABS = os.getenv('OUTPUT_FOLDER')
if not OUTPUT_FOLDER_ABS:
    raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")
if not os.path.isabs(OUTPUT_FOLDER_ABS):
    raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")

# URL paths for HTTP access (relative to server root)
OUTPUT_DIR = "output"
VOXELS_DIR = "voxels"
NIFTI_DIR = "nifti"

# Viewer settings defaults
DEFAULT_VIEWER_SETTINGS = {
    'slice_type': 'Multiplanar',
    'orientation': 'Axial',
    'color_map': 'niivue-ct_translucent',
    'nifti_opacity': 0.7,  # Default CT scan opacity (will be increased when voxels are shown)
    'nifti_gamma': 1.0,
    'show_overlay': False,
    'segment_opacity': 0.8,  # High voxel visibility with good contrast against brighter background
    'segment_gamma': 0.7,   # Lower gamma = brighter voxels
    'window_center': 0,
    'window_width': 1000,
    'volume_rendering': False,
    'volume_opacity': 0.8,
    'volume_gamma': 1.0,
    'lighting_enabled': True,
    'material_shininess': 0.5,
    'view_fit_zoom': 3.0,  # Zoom factor for fitting view to show more of CT scan
    'auto_fit_view': True,  # Automatically fit view to show more of the volume
}

# Slice type mappings
SLICE_TYPE_MAP = {
    "Axial": 0,
    "Coronal": 1,
    "Sagittal": 2,
    "Multiplanar": 3,
    "3D Render": 4
}

# Window presets for CT imaging - Enhanced for better tissue visualization
WINDOW_PRESETS_CT = {
    "Custom": (0, 1000),
    "Standard (W:1000, L:0)": (0, 1000),
    "Soft Tissue (W:400, L:40)": (40, 400),
    "Bone (W:1500, L:300)": (300, 1500),
    "Lung (W:1500, L:-600)": (-600, 1500),
    "Air/Background (W:500, L:-1000)": (-1000, 500),
    "CT Brain (W:80, L:40)": (40, 80),
    "CT Brain Soft (W:100, L:30)": (30, 100),
    "CT Brain Bone (W:2000, L:300)": (300, 2000),
    "CT Chest (W:350, L:50)": (50, 350),
    "CT Abdomen (W:350, L:40)": (40, 350),
    "CT Pelvis (W:350, L:40)": (40, 350),
    "CT Angiography (W:600, L:300)": (300, 600),
    "CT Liver (W:150, L:50)": (50, 150),
    "CT Kidney (W:350, L:40)": (40, 350),
    "CT Spine (W:1800, L:400)": (400, 1800),
    "CT Skull (W:4000, L:700)": (700, 4000)
}

# Window presets for MRI imaging
WINDOW_PRESETS_MRI = {
    "Custom": (360, 720),
    "Standard (W:720, L:360)": (360, 720),
    "T1 Weighted (W:500, L:250)": (250, 500),
    "T2 Weighted (W:800, L:400)": (400, 800),
    "High Contrast (W:300, L:150)": (150, 300),
    "Low Contrast (W:1000, L:500)": (500, 1000)
}

# Combined window presets (legacy support)
WINDOW_PRESETS = WINDOW_PRESETS_CT.copy()
WINDOW_PRESETS.update(WINDOW_PRESETS_MRI)

# Default window settings by modality
DEFAULT_WINDOW_SETTINGS = {
    'CT': {'window_center': 0, 'window_width': 1000},
    'MRI': {'window_center': 360, 'window_width': 720}
}

def detect_modality_from_data(min_value: float, max_value: float, mean_value: float) -> str:
    """
    Detect imaging modality based on data characteristics.
    
    Args:
        min_value: Minimum pixel value in the dataset
        max_value: Maximum pixel value in the dataset  
        mean_value: Mean pixel value in the dataset
        
    Returns:
        'CT' or 'MRI' based on data characteristics
    """
    # CT scans typically have negative values (HU scale) and wider dynamic range
    # MRI scans typically have positive values and smaller dynamic range
    dynamic_range = max_value - min_value
    
    # CT characteristics: negative values, wide dynamic range (>1000)
    if min_value < -100 and dynamic_range > 1000:
        return 'CT'
    # MRI characteristics: positive values, smaller dynamic range (<1000)
    elif min_value >= 0 and dynamic_range < 1000:
        return 'MRI'
    # Default fallback based on mean value
    elif mean_value < 0:
        return 'CT'
    else:
        return 'MRI'

def get_optimal_window_settings(min_value: float, max_value: float, mean_value: float) -> tuple:
    """
    Get optimal window center and width based on data characteristics.
    
    Args:
        min_value: Minimum pixel value in the dataset
        max_value: Maximum pixel value in the dataset
        mean_value: Mean pixel value in the dataset
        
    Returns:
        Tuple of (window_center, window_width)
    """
    modality = detect_modality_from_data(min_value, max_value, mean_value)
    
    if modality == 'CT':
        # For CT, use standard windowing around mean
        window_center = mean_value
        window_width = max(1000, (max_value - min_value) * 0.8)
    else:  # MRI
        # For MRI, center around mean with appropriate width
        window_center = mean_value
        window_width = min(800, (max_value - min_value) * 0.6)
    
    return int(window_center), int(window_width)

# Built-in NiiVue colormaps (as described in issue #83)
BUILTIN_NIIVUE_COLORMAPS = {
    'gray': {'__builtin__': True},
    'jet': {'__builtin__': True},
    'hot': {'__builtin__': True},
    'cool': {'__builtin__': True},
    'warm': {'__builtin__': True},
    'spring': {'__builtin__': True},
    'summer': {'__builtin__': True},
    'autumn': {'__builtin__': True},
    'winter': {'__builtin__': True},
    'rainbow': {'__builtin__': True},
    'viridis': {'__builtin__': True},
    'plasma': {'__builtin__': True},
    'magma': {'__builtin__': True},
    'inferno': {'__builtin__': True},
    'parula': {'__builtin__': True},
    'turbo': {'__builtin__': True},
    'hsv': {'__builtin__': True},
    'bone': {'__builtin__': True},
    'copper': {'__builtin__': True},
    'cubehelix': {'__builtin__': True},
    'cividis': {'__builtin__': True},
    'linspecer': {'__builtin__': True},
    'batlow': {'__builtin__': True},
    'blues': {'__builtin__': True}
}

# Color maps available for NIfTI images
def load_colormaps():
    """Load colormap names from JSON files."""
    import json
    import os
    import glob
    
    # Get all available colormaps from the JSON files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    colormaps_dir = os.path.join(current_dir, '..', 'assets', 'colormaps')
    colormaps_dir = os.path.abspath(colormaps_dir)
    
    if not os.path.exists(colormaps_dir):
        raise FileNotFoundError(f"Colormaps directory not found: {colormaps_dir}")
    
    colormap_files = glob.glob(os.path.join(colormaps_dir, '*.json'))
    
    if not colormap_files:
        raise FileNotFoundError(f"No colormap JSON files found in: {colormaps_dir}")
    
    available_colormaps = set()
    for colormap_file in colormap_files:
        try:
            with open(colormap_file, 'r') as cf:
                data = json.load(cf)
                # Check if this is a collection file with 'colormaps' key
                if 'colormaps' in data and isinstance(data['colormaps'], dict):
                    available_colormaps.update(data['colormaps'].keys())
                # Check if this is an individual colormap file with required fields
                elif all(key in data for key in ['R', 'G', 'B', 'A']):
                    # Extract colormap name from filename (without .json extension)
                    colormap_name = os.path.splitext(os.path.basename(colormap_file))[0]
                    available_colormaps.add(colormap_name)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load colormaps from {colormap_file}: {e}")
            continue
    
    if not available_colormaps:
        raise ValueError("No valid colormaps found in JSON files")
    
    # Return sorted list with medical imaging colormaps first, then rest alphabetically
    colormap_list = sorted(list(available_colormaps))
    
    # Prioritize medical imaging colormaps
    medical_colormaps = [
        'mri_brain_clear',
        'mri_anatomy',
        'fixed_anatomy',
        'working_anatomy',
        'distinct_anatomy',
        'vivid_anatomy',
        'clear_anatomy',
        'medical_anatomy',
        'brain_vessels_eyes',
        'enhanced_brain_anatomy',
        'brain_vessels_clear',
        'niivue-ct_translucent',
        'niivue-ct_soft_tissue', 
        'niivue-ct_brain',
        'niivue-ct_bones',
        'niivue-ct_vessels',
        'realistic_arteries',
        'realistic_veins',
        'realistic_vessels_unified',
        'niivue-ct_liver',
        'niivue-ct_kidneys',
        'niivue-ct_lung',
        'niivue-ct_muscles',
        'niivue-ct_skull',
        'niivue-ct_scalp',
        'niivue-ct_soft',
        'niivue-ct_w_contrast',
        'niivue-ct_enhanced',
        'niivue-ct_metallic',
        'niivue-ct_brain_metallic',
        'niivue-ct_artery',
        'niivue-ct_air',
        'niivue-gray',
        'gray'
    ]
    
    # Reorder to put medical colormaps first
    reordered_list = []
    for colormap in medical_colormaps:
        if colormap in colormap_list:
            reordered_list.append(colormap)
            colormap_list.remove(colormap)
    
    # Add remaining colormaps alphabetically
    reordered_list.extend(sorted(colormap_list))
    
    return reordered_list

def load_colormap_data(colormap_name):
    """Load colormap data from JSON files for a specific colormap name."""
    import json
    import os
    import glob
    
    # Check if this is a built-in colormap first
    if colormap_name in BUILTIN_NIIVUE_COLORMAPS:
        return BUILTIN_NIIVUE_COLORMAPS[colormap_name]
    
    # Get all available colormaps from the JSON files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    colormaps_dir = os.path.join(current_dir, '..', 'assets', 'colormaps')
    colormaps_dir = os.path.abspath(colormaps_dir)
    
    if not os.path.exists(colormaps_dir):
        raise FileNotFoundError(f"Colormaps directory not found: {colormaps_dir}")
    
    colormap_files = glob.glob(os.path.join(colormaps_dir, '*.json'))
    
    for colormap_file in colormap_files:
        try:
            with open(colormap_file, 'r') as cf:
                data = json.load(cf)
                # Check if this is a collection file with 'colormaps' key
                if 'colormaps' in data and isinstance(data['colormaps'], dict):
                    if colormap_name in data['colormaps']:
                        return data['colormaps'][colormap_name]
                # Check if this is an individual colormap file with required fields
                elif all(key in data for key in ['R', 'G', 'B', 'A']):
                    # Extract colormap name from filename (without .json extension)
                    file_colormap_name = os.path.splitext(os.path.basename(colormap_file))[0]
                    if file_colormap_name == colormap_name:
                        return data
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load colormaps from {colormap_file}: {e}")
            continue
    
    # Fallback to gray colormap if not found
    print(f"Warning: Colormap '{colormap_name}' not found, falling back to 'gray'")
    return load_colormap_data('gray')

def load_3d_render_config(config_name='3d_render_quality'):
    """Load 3D rendering configuration from JSON file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(current_dir, '..', CONFIG_FILES['3d_render_config'])
    config_file = os.path.abspath(config_file)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"3D render config file not found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
            if config_name in data:
                return data[config_name]['settings']
            else:
                # Fallback to quality config if specified config not found
                return data['3d_render_quality']['settings']
    except Exception as e:
        print(f"Error loading 3D render config: {e}")
        # Return default settings if config loading fails
        return {
            'antiAlias': True,
            'volumeRenderQuality': 'high',
            'volumeRenderSteps': 256,
            'lighting': True,
            'ambientLight': 0.3,
            'directionalLight': 0.7,
            'backColor': [0, 0, 0, 1]
        }

# Lazy loading of colormaps - only load when actually needed
_available_colormaps = None

def get_available_colormaps():
    """Get available colormaps, loading them lazily if needed."""
    global _available_colormaps
    if _available_colormaps is None:
        _available_colormaps = load_colormaps()
    return _available_colormaps

# For backward compatibility, create a property-like access
class _ColormapAccessor:
    def __iter__(self):
        return iter(get_available_colormaps())
    
    def __contains__(self, item):
        return item in get_available_colormaps()
    
    def __len__(self):
        return len(get_available_colormaps())
    
    def __getitem__(self, key):
        return get_available_colormaps()[key]

AVAILABLE_COLOR_MAPS = _ColormapAccessor()

# Timeout settings
SERVER_TIMEOUT = 10  # seconds

# Viewer dimensions
VIEWER_HEIGHT = 1000

# UI messages
MESSAGES = {
    'no_voxels_available': "No voxels available for this patient/file.",
    'no_nifti_or_voxels': "Nothing to display. Enable 'Show Scan' or 'Show Segments' with selected structures.",
    'select_patient_file': "Select a patient and file to begin.",
}

# Debug settings
DEBUG_MODE = False

# File size filtering
MIN_FILE_SIZE_MB = 3.5  # Minimum file size in MB for processing

# Segmentation validation and cleanup settings
# These can be overridden via environment variables
ENABLE_SEGMENTATION_VALIDATION = os.getenv('ENABLE_SEGMENTATION_VALIDATION', 'true').lower() in ('true', '1', 'yes', 'on')
ENABLE_SEGMENTATION_CLEANUP = os.getenv('ENABLE_SEGMENTATION_CLEANUP', 'true').lower() in ('true', '1', 'yes', 'on')
MIN_VOXELS_PER_LABEL = int(os.getenv('MIN_VOXELS_PER_LABEL', '10'))
MIN_VOXELS_PER_COMPONENT = int(os.getenv('MIN_VOXELS_PER_COMPONENT', '10'))
MAX_SEGMENTATION_RATIO = float(os.getenv('MAX_SEGMENTATION_RATIO', '0.95'))
MIN_SEGMENTATION_RATIO = float(os.getenv('MIN_SEGMENTATION_RATIO', '0.001'))

# Configuration file paths
CONFIG_FILES = {
    'label_colors': 'conf/vista3d_label_colors.json',
    'label_dict': 'conf/vista3d_label_dict.json',
    'label_sets': 'conf/vista3d_label_sets.json',
    '3d_render_config': 'conf/niivue_3d_render_config.json'
}

# Template paths
TEMPLATE_FILES = {
    'viewer': 'assets/niivue_viewer.html'
}
