import streamlit as st
import streamlit.components.v1 as components
import os
import json
from typing import Optional, List
from dotenv import load_dotenv

# Import our new modules
from utils.config_manager import ConfigManager
from utils.data_manager import DataManager
from utils.voxel_manager import VoxelManager
from utils.viewer_config import ViewerConfig
from utils.template_renderer import TemplateRenderer
from utils.constants import (
    NIFTI_EXTENSIONS, DICOM_EXTENSIONS, IMAGE_EXTENSIONS,
    MESSAGES, VIEWER_HEIGHT, detect_modality_from_data,
    load_colormap_data, SLICE_TYPE_MAP, load_3d_render_config
)

# Import badge components
from assets.vista3d_badge import render_nvidia_vista_card
from assets.hpe_badge import render_hpe_badge
 
 

# --- Initial Setup ---
load_dotenv()
initial_image_server_url = os.getenv('IMAGE_SERVER', 'http://localhost:8888')
initial_external_image_server_url = os.getenv('EXTERNAL_IMAGE_SERVER', 'http://localhost:8888')

# Initialize a temporary DataManager to resolve the internal URL for health checks
# In Docker containers, use the internal hostname directly for container-to-container communication
IMAGE_SERVER_URL = initial_image_server_url


# For external URL, use the environment variable directly (don't let DataManager override it)
EXTERNAL_IMAGE_SERVER_URL = initial_external_image_server_url

# Get output folder from environment - must be absolute path
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER')
if not OUTPUT_FOLDER:
    raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")
if not os.path.isabs(OUTPUT_FOLDER):
    raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")

# Initialize our managers with the resolved URLs
config_manager = ConfigManager()
# Verify label colors are loaded
label_colors_count = len(config_manager.label_colors)
print(f"DEBUG (NiiVue_Viewer): Loaded {label_colors_count} label colors from vista3d_label_colors.json")
if label_colors_count > 0:
    print(f"DEBUG (NiiVue_Viewer): Sample color - {config_manager.label_colors[0]}")
data_manager = DataManager(IMAGE_SERVER_URL)
# For external data manager, force it to use the external URL without trying to find working URLs
external_data_manager = DataManager(EXTERNAL_IMAGE_SERVER_URL, force_external_url=True)
# Use internal data manager for voxel detection (health checks), external for URL display
voxel_manager = VoxelManager(config_manager, data_manager)
viewer_config = ViewerConfig()
viewer_config.from_session_state()  # Load settings from session state
template_renderer = TemplateRenderer()

print(f"DEBUG (NiiVue_Viewer): Final IMAGE_SERVER_URL: {IMAGE_SERVER_URL}")
print(f"DEBUG (NiiVue_Viewer): Final EXTERNAL_IMAGE_SERVER_URL: {EXTERNAL_IMAGE_SERVER_URL}")


# --- Sidebar UI ---
def render_sidebar():
    """Render the sidebar with patient/file selection and viewer settings."""
    with st.sidebar:
        # Patient folders are now directly in the output directory
        patient_folders = data_manager.get_server_data('', 'folders', ('',))
        
        # Debug information - only show if no patient folders found
        if not patient_folders:
            st.warning("No patient folders found. Check if:")
            st.write("1. Image server is running")
            st.write("2. OUTPUT_FOLDER contains patient directories")
            st.write("3. Image server can access the output folder")
            
            # Show debug info only when there's an issue
            with st.expander("Debug Info", expanded=False):
                st.write(f"**Image Server URL:** {IMAGE_SERVER_URL}")
                st.write(f"**External Image Server URL:** {EXTERNAL_IMAGE_SERVER_URL}")
                st.write(f"**Output Folder:** {OUTPUT_FOLDER}")
                st.write(f"**DataManager URL:** {data_manager.image_server_url}")
                st.write(f"**Patient Folders Found:** {len(patient_folders)}")
                
                # Test the actual URL being called
                test_url = f"{data_manager.image_server_url}/output/"
                st.write(f"**Test URL:** {test_url}")
                
                # Try to test the connection directly
                import requests
                try:
                    response = requests.get(test_url, timeout=5)
                    st.write(f"**HTTP Response:** {response.status_code}")
                    if response.status_code == 200:
                        st.write("✅ Server is responding")
                        st.write("**Response preview:**")
                        st.code(response.text[:500] + "..." if len(response.text) > 500 else response.text)
                    else:
                        st.write(f"❌ Server returned HTTP {response.status_code}")
                except Exception as e:
                    st.write(f"❌ Connection error: {e}")
        
        # Only show regular patient folders
        # Add None option at the beginning
        patient_options = [None] + patient_folders
        selected_patient = st.selectbox("Select Patient", patient_options, index=0)

        selected_file = None
        
        if selected_patient:
            # Regular patient folder
            filenames = data_manager.get_server_data(f"{selected_patient}/nifti", 'files', IMAGE_EXTENSIONS)

            # Create display names without .nii.gz extensions
            if filenames:
                display_names = [
                    filename.replace('.nii.gz', '').replace('.nii', '').replace('.dcm', '')
                    for filename in filenames
                ]
                # Add None option at the beginning
                scan_options = [None] + display_names
                selected_display_name = st.selectbox("Select Scan", scan_options, index=0)
                # Map back to the actual filename
                if selected_display_name:
                    selected_index = display_names.index(selected_display_name)
                    selected_file = filenames[selected_index]

        # Display modality type under scan selection in sidebar
        if selected_patient and selected_file:
            # Remove .nii.gz extension to get the base filename for JSON file
            base_filename = selected_file.replace('.nii.gz', '').replace('.nii', '')
            metadata_file_path = os.path.join(OUTPUT_FOLDER, selected_patient, "nifti", f"{base_filename}.json")
            
            if os.path.exists(metadata_file_path):
                try:
                    with open(metadata_file_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Get modality, manufacturer, and study description from metadata
                    modality = metadata.get('Modality', '')
                    manufacturer = metadata.get('Manufacturer', '')
                    study_description = metadata.get('StudyDescription', '')
                    
                    if modality:
                        # Convert DICOM modality codes to readable format
                        if modality == 'MR':
                            modality_display = 'MRI'
                        elif modality == 'CT':
                            modality_display = 'CT'
                        else:
                            modality_display = modality  # Use as-is for other modalities
                        
                        # Build display text with available information
                        display_parts = [f"{modality_display} Scan"]
                        if manufacturer:
                            display_parts.append(f"({manufacturer})")
                        if study_description:
                            display_parts.append(f"- {study_description}")
                        st.sidebar.info(f"{', '.join(display_parts)}")
                    else:
                        st.caption("📊 Unknown Scan Type")
                except Exception as e:
                    # Show error for debugging
                    st.caption(f"⚠️ Could not read scan type: {str(e)}")
            else:
                # Metadata file doesn't exist - show debug info
                st.caption(f"⚠️ Metadata file not found: {metadata_file_path}")

        # Update viewer config with selections
        viewer_config.selected_patient = selected_patient
        viewer_config.selected_file = selected_file

        # Extract data characteristics for modality-specific settings
        min_val, max_val, mean_val = None, None, None
        if selected_patient and selected_file:
            quality_file_path = os.path.join(OUTPUT_FOLDER, selected_patient, "nifti", f"{selected_file}.quality.json")
            if os.path.exists(quality_file_path):
                try:
                    with open(quality_file_path, 'r') as f:
                        quality_data = json.load(f)
                    
                    data_quality = quality_data.get('data_quality', {})
                    min_val = data_quality.get('min_value')
                    max_val = data_quality.get('max_value')
                    mean_val = data_quality.get('mean_value')
                    
                    # Apply optimal window settings immediately when new dataset is selected
                    viewer_config.apply_optimal_window_settings(min_val, max_val, mean_val)
                    
                    # Apply appropriate colormap for the detected modality
                    modality = detect_modality_from_data(min_val, max_val, mean_val)
                    if modality == 'MRI':
                        # Use blues colormap for MRI (works great without cube artifacts)
                        viewer_config._settings['color_map'] = 'blues'
                        # Update session state to reflect the change
                        st.session_state.color_map = 'blues'
                    
                except Exception:
                    # Fallback to None if parsing fails
                    pass

        # Check if voxels are available for this patient
        has_voxels = bool(selected_patient and voxel_manager.has_voxels_for_patient(selected_patient))
        
        # Top-level visibility toggles
        show_scan = st.checkbox(
            "Show Scan",
            value=st.session_state.get('show_scan', True),
            help="Toggle visibility of the main scan volume"
        )
        st.session_state.show_scan = show_scan
        viewer_config._settings['show_scan'] = show_scan
        
        # Show Voxels checkbox - only if voxels are available
        if has_voxels:
            show_voxels = st.checkbox(
                "Show Voxels",
                value=viewer_config._settings.get('show_overlay', False),
                help="Toggle visibility of anatomical structure overlays"
            )
            viewer_config._settings['show_overlay'] = show_voxels
            
            # Voxel selection - inline multiselect with buttons
            if show_voxels and selected_patient and selected_file:
                st.markdown("Select Voxels")
                
                # Get available voxels
                available_ids, id_to_name_map, available_voxel_names = voxel_manager.get_available_voxels(
                    selected_patient, selected_file
                )
                
                if available_voxel_names:
                    # Initialize default selection if not present
                    if 'voxel_multiselect_default' not in st.session_state:
                        st.session_state.voxel_multiselect_default = []
                    
                    # Select All / Clear All buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Select All", use_container_width=True):
                            st.session_state.voxel_multiselect_default = available_voxel_names.copy()
                            st.rerun()
                    with col2:
                        if st.button("Clear All", use_container_width=True):
                            st.session_state.voxel_multiselect_default = []
                            st.rerun()
                    
                    # Multiselect for voxel selection
                    selected_voxels = st.multiselect(
                        "Choose anatomical structures:",
                        available_voxel_names,
                        default=st.session_state.voxel_multiselect_default,
                        label_visibility="collapsed"
                    )
                    
                    # Update session state and viewer config
                    st.session_state.voxel_multiselect_default = selected_voxels
                    st.session_state.selected_individual_voxels = selected_voxels
                    viewer_config.selected_individual_voxels = selected_voxels
                    
                    # Show selection count
                    if selected_voxels:
                        st.caption(f"✓ {len(selected_voxels)} structure(s) selected")
                    else:
                        st.caption("No structures selected")
                else:
                    st.warning("No voxels available for this scan.")
        else:
            # Ensure show_overlay is False if no voxels available
            viewer_config._settings['show_overlay'] = False
        
        # Render viewer settings with data characteristics
        viewer_config.render_sidebar_settings(min_val, max_val, mean_val, has_voxels)

        # Voxel image settings - only show if voxels are visible
        if has_voxels and viewer_config._settings.get('show_overlay', False):
            viewer_config.render_voxel_image_settings()

        # Voxel legend - always show if voxels are available
        if has_voxels:
            viewer_config.render_voxel_legend()

        # Add spacing before badges
        st.sidebar.markdown("---")
        
        # Render Nvidia Vista 3D card in sidebar
        render_nvidia_vista_card()
        # Render HPE AI badge in sidebar
        render_hpe_badge()

    return selected_patient, selected_file


# --- Main Application ---
def render_viewer(selected_patient: str, selected_file: str):
    """Render the main NiiVue viewer."""
    if not selected_file:
        st.info(MESSAGES['select_patient_file'])
        return

    # Prepare volume URLs and overlays
    # Regular patient file
    base_file_url = f"{EXTERNAL_IMAGE_SERVER_URL}/output/{selected_patient}/nifti/{selected_file}"

    # Create overlays from selected voxels
    overlays = []
    if selected_patient:
        # Debug: Check voxel selection state
        print(f"DEBUG: === VOXEL STATE ===")
        print(f"DEBUG: viewer_config.selected_individual_voxels = {viewer_config.selected_individual_voxels}")
        print(f"DEBUG: st.session_state.selected_individual_voxels = {st.session_state.get('selected_individual_voxels', 'NOT SET')}")
        print(f"DEBUG: === END VOXEL STATE ===")
        
        overlays = voxel_manager.create_overlays(
            selected_patient,
            selected_file,
            viewer_config.selected_individual_voxels,
            external_url=EXTERNAL_IMAGE_SERVER_URL
        )
        print(f"DEBUG: Created {len(overlays)} overlays")

    # Build volume list for NiiVue
    volume_list_entries = []
    
    # Include base scan only if "Show Scan" is enabled
    if viewer_config.settings.get('show_scan', True):
        volume_list_entries.append({"url": base_file_url})
        print(f"DEBUG: Added base scan to volume list")

    # Add overlay volumes
    show_overlay = viewer_config.settings.get('show_overlay', False)
    print(f"DEBUG: show_overlay={show_overlay}, overlays count={len(overlays)}")
    
    if show_overlay and overlays:
        for overlay in overlays:
            if overlay.get('url'):
                volume_list_entries.append({"url": overlay['url']})
        print(f"DEBUG: Added {len(overlays)} overlays to volume list")
    elif not show_overlay:
        print(f"DEBUG: Show Voxels checkbox is NOT checked - voxels will not be displayed")
    elif not overlays:
        print(f"DEBUG: No overlays were created")

    if not volume_list_entries:
        st.info(MESSAGES['no_nifti_or_voxels'])
        return

    # Prepare JavaScript data
    volume_list_js = json.dumps(volume_list_entries)
    overlay_colors_js = json.dumps(overlays)
    custom_colormap_js = voxel_manager.create_custom_colormap_js()

    print(f"DEBUG (NiiVue_Viewer): Total volumes to load: {len(volume_list_entries)}")
    print(f"DEBUG (NiiVue_Viewer): Volume list preview: {volume_list_js[:200]}...")


    # Get viewer settings
    settings = viewer_config.settings
    window_center, window_width = viewer_config.get_window_settings()
    # Robustly compute slice type using session state as source of truth
    try:
        slice_type_setting = st.session_state.get('slice_type', settings.get('slice_type', 'Multiplanar'))
        orientation_setting = st.session_state.get('orientation', settings.get('orientation', 'Axial'))
        if slice_type_setting == "Single View":
            actual_slice_type = SLICE_TYPE_MAP.get(orientation_setting, 3)
        else:
            actual_slice_type = SLICE_TYPE_MAP.get(slice_type_setting, 3)
    except Exception:
        # Fallback to existing method
        actual_slice_type = viewer_config.get_slice_type_index()

    print(f"DEBUG (NiiVue_Viewer): slice_type={slice_type_setting} orientation={orientation_setting} actual_slice_type={actual_slice_type}")

    # Persist back to viewer_config settings so template sees the intended values
    viewer_config._settings['slice_type'] = slice_type_setting
    viewer_config._settings['orientation'] = orientation_setting
    segment_opacity = settings.get('segment_opacity', 0.8)
    segment_gamma = settings.get('segment_gamma', 1.0)
    
    # Load the Niivue JavaScript library content
    from pathlib import Path
    niivue_lib_path = Path(__file__).parent / 'assets' / 'niivue.umd.js'
    with open(niivue_lib_path, 'r') as f:
        niivue_lib_content = f.read()
    
    # Load 3D render configuration based on user selection
    selected_preset = settings.get('3d_render_preset', '3d_render_quality')
    render_config = load_3d_render_config(selected_preset)
    
    # Override with user-selected values
    if 'alpha_test' in settings:
        render_config['alphaTest'] = settings['alpha_test']
    if 'transparency_quality' in settings:
        render_config['transparencyQuality'] = settings['transparency_quality']
    if 'depth_precision' in settings:
        render_config['depthPrecision'] = settings['depth_precision']
    
    # Override lighting settings
    if 'ambient_light' in settings:
        render_config['ambientLight'] = settings['ambient_light']
    if 'directional_light' in settings:
        render_config['directionalLight'] = settings['directional_light']
    if all(key in settings for key in ['light_x', 'light_y', 'light_z']):
        render_config['lightPosition'] = [
            settings['light_x'], 
            settings['light_y'], 
            settings['light_z']
        ]
    
    # Override shader effects settings
    if 'ambient_occlusion' in settings:
        render_config['ambientOcclusion'] = settings['ambient_occlusion']
    if 'ao_intensity' in settings:
        render_config['ambientOcclusionIntensity'] = settings['ao_intensity']
    if 'ao_radius' in settings:
        render_config['ambientOcclusionRadius'] = settings['ao_radius']
    
    if 'bloom' in settings:
        render_config['bloom'] = settings['bloom']
    if 'bloom_intensity' in settings:
        render_config['bloomIntensity'] = settings['bloom_intensity']
    if 'bloom_threshold' in settings:
        render_config['bloomThreshold'] = settings['bloom_threshold']
    
    if 'depth_of_field' in settings:
        render_config['depthOfField'] = settings['depth_of_field']
    if 'dof_focus' in settings:
        render_config['depthOfFieldFocus'] = settings['dof_focus']
    if 'dof_blur' in settings:
        render_config['depthOfFieldBlur'] = settings['dof_blur']
    
    if 'vignette' in settings:
        render_config['vignette'] = settings['vignette']
    if 'vignette_intensity' in settings:
        render_config['vignetteIntensity'] = settings['vignette_intensity']
    if 'vignette_radius' in settings:
        render_config['vignetteRadius'] = settings['vignette_radius']
    
    # Render the viewer using our template
    show_scan = settings.get('show_scan', True)
    html_content = template_renderer.render_template(
        'niivue_viewer.html',
        niivue_lib_content=niivue_lib_content,
        volume_list_js=volume_list_js,
        overlay_colors_js=overlay_colors_js,
        custom_colormap_js=custom_colormap_js,
        image_server_url=EXTERNAL_IMAGE_SERVER_URL,
        main_is_nifti=True,
        main_vol=show_scan,  # Only apply main volume logic if scan is shown
        color_map_js=json.dumps(settings.get('color_map', 'niivue-ct_translucent')),
        color_map_data_js=json.dumps(load_colormap_data(settings.get('color_map', 'niivue-ct_translucent'))),
        nifti_gamma=settings.get('nifti_gamma', 1.0),
        nifti_opacity=viewer_config.get_dynamic_nifti_opacity(),
        window_center=window_center,
        window_width=window_width,
        actual_slice_type=actual_slice_type,
        overlay_start_index=1 if show_scan else 0,  # Overlays start after scan if shown
        segment_opacity=segment_opacity,
        segment_gamma=segment_gamma,
        view_fit_zoom=settings.get('view_fit_zoom', 3.0),
        render_config_js=json.dumps(render_config)
    )

    # Display the viewer
    components.html(html_content, height=VIEWER_HEIGHT, scrolling=False)


# --- Main Application Flow ---
def main():
    """Main application entry point."""
    # Set page title
    st.header("🩻 NiiVue Viewer")
    
    # Render sidebar and get selections
    selected_patient, selected_file = render_sidebar()

    # Render main viewer
    render_viewer(selected_patient, selected_file)


if __name__ == "__main__":
    main()
