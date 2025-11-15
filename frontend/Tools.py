import streamlit as st
import subprocess
import os
import sys
from pathlib import Path
import json
import pandas as pd
from typing import Dict, List, Optional
import time

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent / 'utils'))

# Import badge components
from assets.vista3d_badge import render_nvidia_vista_card as _render_nvidia_vista_card
from assets.hpe_badge import render_hpe_badge as _render_hpe_badge

def run_command(command: List[str], description: str = "") -> tuple[bool, str, str]:
    """Run a command and return success status, stdout, and stderr."""
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            cwd=Path(__file__).parent,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after 5 minutes"
    except Exception as e:
        return False, "", f"Error running command: {str(e)}"


def get_dicom_patient_folders() -> List[str]:
    """Get list of patient folders from DICOM directory."""
    try:
        # Load environment variables to get DICOM folder path
        from dotenv import load_dotenv
        # Load .env from project root (parent of frontend directory)
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        # Check if we're running in a Docker container
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        if is_docker:
            # In Docker container, use the mounted paths
            dicom_folder = '/app/dicom'
        else:
            # On host machine, use environment variables
            dicom_folder = os.getenv('DICOM_FOLDER')
            if not dicom_folder:
                return []
        
        dicom_path = Path(dicom_folder)
        
        # Check if DICOM directory exists
        if not dicom_path.exists() or not dicom_path.is_dir():
            return []
        
        # Get list of subdirectories (patient folders)
        patient_folders = []
        for entry in os.scandir(dicom_path):
            if entry.is_dir() and entry.name != 'uploads':
                patient_folders.append(entry.name)
        
        return sorted(patient_folders)
        
    except Exception as e:
        st.error(f"Error getting patient folders: {str(e)}")
        return []


def get_patients_with_nifti_files() -> List[str]:
    """Get list of patient folders that have nii.gz files in their nifti folder."""
    try:
        # Load environment variables to get OUTPUT_FOLDER path
        from dotenv import load_dotenv
        # Load .env from project root (parent of frontend directory)
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        output_folder = os.getenv('OUTPUT_FOLDER')
        if not output_folder:
            return []
        
        output_path = Path(output_folder)
        
        # Check if output directory exists
        if not output_path.exists() or not output_path.is_dir():
            return []
        
        # Get list of patient folders that have nifti files
        patients_with_nifti = []
        for entry in os.scandir(output_path):
            if entry.is_dir() and entry.name != 'uploads':
                patient_id = entry.name
                nifti_dir = output_path / patient_id / "nifti"
                
                # Check if nifti directory exists and contains nii.gz files
                if nifti_dir.exists() and nifti_dir.is_dir():
                    has_nifti_files = False
                    try:
                        for nifti_file in os.scandir(nifti_dir):
                            if nifti_file.is_file() and nifti_file.name.endswith('.nii.gz'):
                                has_nifti_files = True
                                break
                    except (PermissionError, OSError):
                        # Skip if we can't access the directory
                        continue
                    
                    if has_nifti_files:
                        patients_with_nifti.append(patient_id)
        
        return sorted(patients_with_nifti)
        
    except Exception as e:
        st.error(f"Error getting patients with NIfTI files: {str(e)}")
        return []


def get_scans_for_patient(patient_id: str) -> List[str]:
    """Get list of scan files (nii.gz) for a specific patient."""
    try:
        # Load environment variables to get OUTPUT_FOLDER path
        from dotenv import load_dotenv
        # Load .env from project root (parent of frontend directory)
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        output_folder = os.getenv('OUTPUT_FOLDER')
        if not output_folder:
            return []
        
        output_path = Path(output_folder)
        nifti_dir = output_path / patient_id / "nifti"
        
        # Check if nifti directory exists
        if not nifti_dir.exists() or not nifti_dir.is_dir():
            return []
        
        # Get list of nii.gz files
        scan_files = []
        try:
            for nifti_file in os.scandir(nifti_dir):
                if nifti_file.is_file() and nifti_file.name.endswith('.nii.gz'):
                    # Remove .nii.gz extension for display
                    display_name = nifti_file.name.replace('.nii.gz', '')
                    scan_files.append(display_name)
        except (PermissionError, OSError):
            return []
        
        return sorted(scan_files)
        
    except Exception as e:
        st.error(f"Error getting scans for patient {patient_id}: {str(e)}")
        return []






def render_dicom_tools():
    """Render DICOM processing tools."""
    st.subheader("📋 DICOM Processing Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        pass
    
    with col2:
        st.markdown("**DICOM to NIfTI Converter**")
        st.markdown("Convert DICOM files to NIfTI format")
        if st.button("Run DICOM2NIfTI", key="dicom2nifti"):
            with st.spinner("Converting DICOM files..."):
                success, stdout, stderr = run_command(
                    ["python", "utils/dicom2nifti.py"],
                    "DICOM to NIfTI conversion"
                )
                
                if success:
                    st.success("✅ DICOM conversion completed successfully!")
                    if stdout:
                        st.text_area("Output:", stdout, height=200, key="dicom_output_stdout")
                else:
                    st.error("❌ DICOM conversion failed!")
                    if stderr:
                        st.text_area("Error:", stderr, height=200, key="dicom_output_stderr")




def render_segmentation_tools():
    """Render segmentation tools."""
    st.subheader("🎯 Vista3D Segmentation")
    st.markdown("""
    Run Vista3D AI segmentation on medical images to identify and segment anatomical structures.
    This tool processes NIfTI files and creates detailed segmentation masks with individual voxel files.
    """)
    
    # Segmentation options
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Segmentation Options**")
        
        # Patient selection - only show patients with nifti files
        patient_folders = get_patients_with_nifti_files()
        
        if not patient_folders:
            st.warning("⚠️ No patient folders with NIfTI files found. Please check your OUTPUT_FOLDER path in .env file and ensure patients have been processed through DICOM to NIfTI conversion.")
            return
        
        # Get previously selected patients to detect changes
        prev_selected_patients = st.session_state.get("segmentation_patients", [])
        
        selected_patients = st.multiselect(
            "Select Patients",
            options=patient_folders,
            default=patient_folders,  # Select all by default
            help="Select one or more patient folders to process. Leave empty or uncheck all to process no patients.",
            key="segmentation_patients"
        )
        
        # Check if patients were deselected and clear invalid scans
        if selected_patients != prev_selected_patients:
            # Patients changed, need to update available scans
            if "segmentation_scans" in st.session_state:
                # Get current available scans for selected patients
                current_available_scans = []
                for patient in selected_patients:
                    scans = get_scans_for_patient(patient)
                    current_available_scans.extend(scans)
                current_available_scans = list(dict.fromkeys(current_available_scans))
                
                # Filter out scans that are no longer available
                valid_scans = [scan for scan in st.session_state["segmentation_scans"] if scan in current_available_scans]
                st.session_state["segmentation_scans"] = valid_scans
        
        # Scan selection - show available scans for selected patients
        selected_scans = []
        if selected_patients:
            st.markdown("**Select Scans**")
            all_available_scans = []
            patient_scan_map = {}
            
            for patient in selected_patients:
                scans = get_scans_for_patient(patient)
                patient_scan_map[patient] = scans
                all_available_scans.extend(scans)
            
            # Remove duplicates while preserving order
            unique_scans = list(dict.fromkeys(all_available_scans))
            
            if unique_scans:
                # Get previously selected scans from session state
                prev_selected_scans = st.session_state.get("segmentation_scans", [])
                
                # Filter previously selected scans to only include those available for current patients
                valid_prev_scans = [scan for scan in prev_selected_scans if scan in unique_scans]
                
                # If no valid previous selections, default to all scans
                default_scans = valid_prev_scans if valid_prev_scans else unique_scans
                
                selected_scans = st.multiselect(
                    "Select Scans to Process",
                    options=unique_scans,
                    default=default_scans,
                    help="Select specific scans to process. Leave empty or uncheck all to process no scans.",
                    key="segmentation_scans"
                )
            else:
                st.warning("No scans found for selected patients.")
                # Clear any previously selected scans if no scans available
                if "segmentation_scans" in st.session_state:
                    st.session_state["segmentation_scans"] = []
        else:
            # No patients selected, clear any previously selected scans
            if "segmentation_scans" in st.session_state:
                st.session_state["segmentation_scans"] = []
        
        # Force overwrite option
        force_overwrite = st.checkbox(
            "Force Overwrite", 
            value=False, 
            help="Overwrite existing segmentation files"
        )
        
        # Vessels of interest
        vessels_of_interest = st.text_input(
            "Vessels of Interest", 
            value="", 
            placeholder="Leave empty for all vessels (default) or specify: aorta, inferior_vena_cava",
            help="Leave empty to process ALL available vessels (default). Or specify a comma-separated list of specific vessels to segment."
        )
        
        # Label set selection
        label_set = st.selectbox(
            "Label Set",
            options=["", "basic", "extended", "custom"],
            help="Select a predefined label set for segmentation"
        )
    
    with col2:
        # Display patient and scan info
        if not selected_patients:
            st.warning("⚠️ **No patients selected**")
            st.markdown("Please select at least one patient to process.")
        elif not selected_scans:
            st.warning("⚠️ **No scans selected**")
            st.markdown("Please select at least one scan to process.")
        else:
            if len(selected_patients) == len(patient_folders):
                st.info(f"📁 **Patients:** All {len(patient_folders)} patients")
            elif len(selected_patients) == 1:
                st.info(f"📁 **Patients:** {selected_patients[0]}")
            else:
                st.info(f"📁 **Patients:** {len(selected_patients)} patients")
            
            if len(selected_scans) == 1:
                st.info(f"🔬 **Scans:** {selected_scans[0]}")
            else:
                st.info(f"🔬 **Scans:** {len(selected_scans)} scans")
        
        # Disable button if no patients or scans selected
        button_disabled = len(selected_patients) == 0 or len(selected_scans) == 0
        
        segmentation_clicked = st.button("🎯 Start Vista3D Segmentation", key="start_segmentation", type="primary", disabled=button_disabled)
    
    # Check if segmentation button was clicked
    if segmentation_clicked:
        with st.spinner("Starting Vista3D segmentation..."):
            # Prepare command arguments
            cmd_args = ["python", "utils/segment.py"]
            
            # Add patient selection if specific patients are chosen
            if len(selected_patients) < len(patient_folders):
                # Add selected patients as arguments
                cmd_args.extend(selected_patients)
            
            if force_overwrite:
                cmd_args.append("--force")
            
            # Create progress containers
            progress_container = st.container()
            output_container = st.container()
            
            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()
            
            with output_container:
                output_placeholder = st.empty()
            
            try:
                # Set environment variables if specified
                env = os.environ.copy()
                if vessels_of_interest:
                    env['VESSELS_OF_INTEREST'] = vessels_of_interest
                if label_set:
                    env['LABEL_SET'] = label_set
                if selected_scans:
                    # Pass selected scans as comma-separated list
                    env['SELECTED_SCANS'] = ','.join(selected_scans)
                
                # Run the segmentation with real-time output
                status_text.text("🎯 Initializing Vista3D segmentation...")
                progress_bar.progress(10)
                
                # Start the subprocess
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=Path(__file__).parent,
                    env=env
                )
                
                # Read output line by line
                output_lines = []
                current_progress = 10
                
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_lines.append(output.strip())
                        # Update output display (keep last 20 lines)
                        recent_output = output_lines[-20:]
                        output_placeholder.text_area(
                            "Segmentation Output:", 
                            value="\n".join(recent_output), 
                            height=300,
                            disabled=True,
                            key=f"segmentation_output_realtime_{len(output_lines)}"
                        )
                        
                        # Update progress based on output keywords
                        if "Processing patients" in output:
                            current_progress = min(30, current_progress + 5)
                        elif "Processing NIfTI files" in output:
                            current_progress = min(60, current_progress + 10)
                        elif "Successfully saved segmentation" in output:
                            current_progress = min(90, current_progress + 15)
                        elif "Segmentation Process Complete" in output:
                            current_progress = 100
                        
                        progress_bar.progress(current_progress)
                        if len(selected_patients) == len(patient_folders):
                            status_text.text(f"🎯 Running Vista3D segmentation for all patients and {len(selected_scans)} scans... ({current_progress}%)")
                        elif len(selected_patients) == 1:
                            status_text.text(f"🎯 Running Vista3D segmentation for {selected_patients[0]} with {len(selected_scans)} scans... ({current_progress}%)")
                        else:
                            status_text.text(f"🎯 Running Vista3D segmentation for {len(selected_patients)} patients with {len(selected_scans)} scans... ({current_progress}%)")
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    progress_bar.progress(100)
                    status_text.text("✅ Segmentation completed successfully!")
                    st.info("Vista3D segmentation completed successfully!")
                    st.balloons()
                    
                    # Show final output
                    final_output = "\n".join(output_lines)
                    st.text_area("Final Output:", final_output, height=400, disabled=True, key="segmentation_output_final")
                    
                else:
                    progress_bar.progress(0)
                    status_text.text("❌ Segmentation failed!")
                    st.error("❌ Vista3D segmentation failed!")
                    
                    # Show error output
                    error_output = "\n".join(output_lines)
                    st.text_area("Error Output:", error_output, height=400, disabled=True, key="segmentation_error_output")
                    
            except Exception as e:
                progress_bar.progress(0)
                status_text.text("❌ Segmentation error!")
                st.error(f"❌ Error running segmentation: {str(e)}")
                
                # Show error details
                st.text_area("Error Details:", str(e), height=200, disabled=True, key="segmentation_error_details")


def main():
    """Main function to render the Tools page."""
    # Note: st.set_page_config() is handled by the main app.py
    # Only set page config when running as standalone
    if __name__ == "__main__":
        st.set_page_config(
            page_title="Tools - HPE-NVIDIA Vista 3D",
            page_icon="🛠️",
            layout="wide"
        )
    
    st.title("🛠️ Tools & Utilities")
    st.markdown("Access various tools and utilities for medical image processing and 3D visualization.")
    
    st.markdown("---")
    
    # DICOM to NIfTI Conversion Section
    st.subheader("🔄 DICOM to NIfTI Conversion")
    st.markdown("""
    Convert DICOM medical imaging files to NIfTI format using dcm2niix. This tool processes 
    DICOM files and creates optimized NIfTI files with metadata for medical image analysis.
    """)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Patient selection
        patient_folders = get_dicom_patient_folders()
        
        if not patient_folders:
            st.warning("⚠️ No patient folders found in DICOM directory. Please check your DICOM_FOLDER path in .env file.")
            return
        
        selected_patients = st.multiselect(
            "Select Patients",
            options=patient_folders,
            default=patient_folders,  # Select all by default
            help="Select one or more patient folders to process. Leave empty or uncheck all to process no patients."
        )
        
        # Conversion options
        force_overwrite = st.checkbox("Force Overwrite", value=False, help="Overwrite existing NIfTI files")
        min_size_mb = st.number_input("Minimum File Size (MB)", min_value=0.0, value=5.0, step=0.1, 
                                    help="Delete NIfTI files smaller than this size")
        
        # Maximum quality mode is always enabled
    
    with col2:
        # Display patient info
        if not selected_patients:
            st.warning("⚠️ **No patients selected**")
            st.markdown("Please select at least one patient to process.")
        elif len(selected_patients) == len(patient_folders):
            st.info(f"📁 **Processing:** All {len(patient_folders)} patients")
        elif len(selected_patients) == 1:
            st.info(f"📁 **Processing:** {selected_patients[0]}")
        else:
            st.info(f"📁 **Processing:** {len(selected_patients)} patients")
        
        # Disable button if no patients selected
        button_disabled = len(selected_patients) == 0
        
        conversion_clicked = st.button("🔄 Start DICOM to NIfTI Conversion", key="start_dicom2nifti", type="primary", disabled=button_disabled)
    
    # Check if conversion button was clicked
    if conversion_clicked:
        with st.spinner("Starting DICOM to NIfTI conversion..."):
            # Prepare command arguments
            cmd_args = ["python", "utils/dicom2nifti.py"]
            
            if force_overwrite:
                cmd_args.append("--force")
            
            if min_size_mb > 0:
                cmd_args.extend(["--min-size-mb", str(int(min_size_mb))])
            
            # Maximum quality mode is always enabled
            
            # Add patient selection if specific patients are chosen
            if len(selected_patients) < len(patient_folders):
                # Specific patients selected - use --patient argument
                cmd_args.extend(["--patient"] + selected_patients)
            
            # Create progress containers
            progress_container = st.container()
            output_container = st.container()
            
            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()
            
            with output_container:
                output_placeholder = st.empty()
            
            try:
                # Run the conversion with real-time output
                status_text.text("🔄 Initializing conversion...")
                progress_bar.progress(10)
                
                # Start the subprocess
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=Path(__file__).parent
                )
                
                # Read output line by line
                output_lines = []
                current_progress = 10
                
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_lines.append(output.strip())
                        # Update output display (keep last 20 lines)
                        recent_output = output_lines[-20:]
                        output_placeholder.text_area(
                            "Conversion Output:", 
                            value="\n".join(recent_output), 
                            height=300,
                            disabled=True,
                            key=f"dicom2nifti_output_realtime_{len(output_lines)}"
                        )
                        
                        # Update progress based on output keywords
                        if "Processing patients" in output or "Processing specific patient" in output:
                            current_progress = min(50, current_progress + 5)
                        elif "Successfully processed" in output:
                            current_progress = min(90, current_progress + 10)
                        elif "conversion completed" in output:
                            current_progress = 100
                        
                        progress_bar.progress(current_progress)
                        if len(selected_patients) == len(patient_folders):
                            status_text.text(f"🔄 Converting DICOM files for all patients... ({current_progress}%)")
                        elif len(selected_patients) == 1:
                            status_text.text(f"🔄 Converting DICOM files for {selected_patients[0]}... ({current_progress}%)")
                        else:
                            status_text.text(f"🔄 Converting DICOM files for {len(selected_patients)} patients... ({current_progress}%)")
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    progress_bar.progress(100)
                    status_text.text("✅ Conversion completed successfully!")
                    st.info("DICOM to NIfTI conversion completed successfully!")
                    st.balloons()
                    
                    # Show final output
                    final_output = "\n".join(output_lines)
                    st.text_area("Final Output:", final_output, height=400, disabled=True, key="dicom2nifti_output_final")
                    
                else:
                    progress_bar.progress(0)
                    status_text.text("❌ Conversion failed!")
                    st.error("❌ DICOM to NIfTI conversion failed!")
                    
                    # Show error output
                    error_output = "\n".join(output_lines)
                    st.text_area("Error Output:", error_output, height=400, disabled=True, key="dicom2nifti_error_output")
                    
            except Exception as e:
                progress_bar.progress(0)
                status_text.text("❌ Conversion error!")
                st.text_area("Error Details:", str(e), height=200, disabled=True, key="dicom2nifti_error_details")
    
    st.markdown("---")
    
    # Vista3D Segmentation Section
    render_segmentation_tools()
    
    
    # Render badges in sidebar
    st.sidebar.markdown("---")
    _render_nvidia_vista_card()
    _render_hpe_badge()

if __name__ == "__main__":
    main()
