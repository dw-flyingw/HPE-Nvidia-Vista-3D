import streamlit as st
import streamlit.components.v1 as components
import os
import json
from typing import Optional
from dotenv import load_dotenv

# Import our new modules
from utils.config_manager import ConfigManager
from utils.data_manager import DataManager
from utils.voxel_manager import VoxelManager
from utils.viewer_config import ViewerConfig
from utils.template_renderer import TemplateRenderer
from utils.constants import (
    NIFTI_EXTENSIONS, DICOM_EXTENSIONS, IMAGE_EXTENSIONS,
    VOXEL_MODES, MESSAGES, VIEWER_HEIGHT, detect_modality_from_data
)
 
 

# --- Initial Setup ---
load_dotenv()
IMAGE_SERVER_URL = os.getenv('IMAGE_SERVER', 'http://localhost:8888')
EXTERNAL_IMAGE_SERVER_URL = os.getenv('EXTERNAL_IMAGE_SERVER', 'http://localhost:8888')

# Initialize our managers
config_manager = ConfigManager()
data_manager = DataManager(IMAGE_SERVER_URL)
external_data_manager = DataManager(EXTERNAL_IMAGE_SERVER_URL)
voxel_manager = VoxelManager(config_manager, external_data_manager)
viewer_config = ViewerConfig()
template_renderer = TemplateRenderer()


# --- Sidebar UI ---
def render_sidebar():
    """Render the sidebar with patient/file selection and viewer settings."""
    with st.sidebar:
        # Patient folders are now directly in the output directory
        patient_folders = data_manager.get_server_data('', 'folders', ('',))
        # Add None option at the beginning
        patient_options = [None] + patient_folders
        selected_patient = st.selectbox("Select Patient", patient_options, index=0)

        selected_file = None
        if selected_patient:
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

        # Update viewer config with selections
        viewer_config.selected_patient = selected_patient
        viewer_config.selected_file = selected_file

        # Extract data characteristics for modality-specific settings
        min_val, max_val, mean_val = None, None, None
        if selected_patient and selected_file:
            output_folder = os.getenv('OUTPUT_FOLDER', 'output')
            quality_file_path = os.path.join(output_folder, selected_patient, "nifti", f"{selected_file}.quality.json")
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
                        # Use bone colormap for MRI (works great without cube artifacts)
                        viewer_config._settings['color_map'] = 'bone'
                    
                except Exception:
                    # Fallback to None if parsing fails
                    pass

        # Check if voxels are available for this patient
        has_voxels = bool(selected_patient and voxel_manager.has_voxels_for_patient(selected_patient))
        
        # Render viewer settings with data characteristics
        viewer_config.render_sidebar_settings(min_val, max_val, mean_val, has_voxels)

        # Only show voxel settings if there are voxels available for this patient
        if has_voxels:
            # Voxel selection (after show_overlay is set)
            if viewer_config.settings.get('show_overlay', False):
                render_voxel_selection(selected_patient, selected_file)
                # Voxel image settings (after voxel selection)
                viewer_config.render_voxel_image_settings()

            # Voxel legend
            viewer_config.render_voxel_legend()

    return selected_patient, selected_file


def render_voxel_selection(selected_patient: str, selected_file: str):
    """Render the voxel selection interface."""
    with st.expander("Select Voxels", expanded=False):
        # Voxel selection mode
        voxel_mode = st.radio(
            "Choose voxel selection mode:",
            VOXEL_MODES,
            index=0,
            help="Select how you want to choose which voxels to display"
        )

        # Get available voxel information
        available_ids, id_to_name_map, available_voxel_names = voxel_manager.get_available_voxels(
            selected_patient, selected_file, voxel_mode
        )

        # Handle voxel mode selection
        if voxel_mode == "All":
            st.info("Will display the complete base segmentation file.")
            viewer_config.voxel_mode = "all"
            viewer_config.selected_individual_voxels = []

        elif voxel_mode == "Individual Voxels":
            if not available_ids:
                # Show warning if no voxels available
                voxels_url = data_manager.get_voxel_directory_url(selected_patient, selected_file)
                st.warning("No voxels available for this patient/file.")
                st.caption(f"Voxels directory: {voxels_url}")
                st.caption("Individual voxel files should be located in this directory.")
            else:
                # Show voxel selection interface
                selected_voxels = st.multiselect(
                    "Choose individual voxels to overlay:",
                    available_voxel_names,
                    default=[],
                    help="Select specific anatomical structures to display"
                )

                # Display selection status
                if selected_voxels:
                    st.info(f"Will display {len(selected_voxels)} individual voxels from the voxels directory.")
                else:
                    st.info("No individual voxels selected. Select specific structures to display.")

                viewer_config.voxel_mode = "individual_voxels"
                viewer_config.selected_individual_voxels = selected_voxels

        # Update session state
        viewer_config.to_session_state()

    # Display current voxel selection status
    status_message = viewer_config.get_status_message()
    if status_message:
        st.info(status_message)


# --- Main Application ---
def render_viewer(selected_patient: str, selected_file: str):
    """Render the main NiiVue viewer."""
    if not selected_file:
        st.info(MESSAGES['select_patient_file'])
        return

    # Prepare volume URLs and overlays
    output_folder = os.getenv('OUTPUT_FOLDER', 'output')
    base_file_url = f"{EXTERNAL_IMAGE_SERVER_URL}/{output_folder}/{selected_patient}/nifti/{selected_file}"

    # Create overlays based on voxel mode
    overlays = voxel_manager.create_overlays(
        selected_patient,
        selected_file,
        viewer_config.voxel_mode,
        viewer_config.selected_individual_voxels
    )

    # Build volume list for NiiVue
    volume_list_entries = []
    if viewer_config.settings.get('show_nifti', True):
        volume_list_entries.append({"url": base_file_url})

    # Add overlay volumes
    if viewer_config.settings.get('show_overlay', False) and overlays:
        for overlay in overlays:
            if overlay.get('url'):
                volume_list_entries.append({"url": overlay['url']})

    if not volume_list_entries:
        st.info(MESSAGES['no_nifti_or_voxels'])
        return

    # Prepare JavaScript data
    volume_list_js = json.dumps(volume_list_entries)
    overlay_colors_js = json.dumps(overlays)
    custom_colormap_js = voxel_manager.create_custom_colormap_js()


    # Get viewer settings
    settings = viewer_config.settings
    window_center, window_width = viewer_config.get_window_settings()
    actual_slice_type = viewer_config.get_slice_type_index()

# Removed unused debug checkbox

    # Render the viewer using our template
    html_content = template_renderer.render_viewer(
        volume_list_js=volume_list_js,
        overlay_colors_js=overlay_colors_js,
        custom_colormap_js=custom_colormap_js,
        image_server_url=EXTERNAL_IMAGE_SERVER_URL,
        main_is_nifti=settings.get('show_nifti', True),
        main_vol=settings.get('show_nifti', True),
        color_map_js=json.dumps(settings.get('color_map', 'gray')),
        nifti_gamma=settings.get('nifti_gamma', 1.0),
        nifti_opacity=settings.get('nifti_opacity', 1.0),
        window_center=window_center,
        window_width=window_width,
        overlay_start_index=1 if settings.get('show_nifti', True) else 0,
        actual_slice_type=actual_slice_type,
        segment_opacity=settings.get('segment_opacity', 0.5)
    )

    # Display the viewer
    components.html(html_content, height=VIEWER_HEIGHT, scrolling=False)


# --- Main Application Flow ---
def main():
    """Main application entry point."""
    # Set page title
    st.title("🩻 NiiVue Viewer")
    
    # Render sidebar and get selections
    selected_patient, selected_file = render_sidebar()

    # Render main viewer
    render_viewer(selected_patient, selected_file)


if __name__ == "__main__":
    main()
