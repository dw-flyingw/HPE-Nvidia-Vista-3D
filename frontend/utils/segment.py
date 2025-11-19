import tempfile
import os
import requests
import json
import argparse
from pathlib import Path
from tqdm import tqdm
import nibabel as nib
import gzip
import zipfile
import io
import numpy as np
import traceback
import shutil
from typing import List, Dict, Any
from dotenv import load_dotenv
try:
    from utils.config_manager import ConfigManager
    from utils.constants import (
        MIN_FILE_SIZE_MB,
        ENABLE_SEGMENTATION_VALIDATION,
        ENABLE_SEGMENTATION_CLEANUP,
        MIN_VOXELS_PER_LABEL,
        MIN_VOXELS_PER_COMPONENT,
        MAX_SEGMENTATION_RATIO,
        MIN_SEGMENTATION_RATIO
    )
    from utils.segmentation_validator import validate_and_clean
except ModuleNotFoundError:
    # Allow running as a script: python utils/segment.py
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parents[1]))
    from utils.config_manager import ConfigManager
    from utils.constants import (
        MIN_FILE_SIZE_MB,
        ENABLE_SEGMENTATION_VALIDATION,
        ENABLE_SEGMENTATION_CLEANUP,
        MIN_VOXELS_PER_LABEL,
        MIN_VOXELS_PER_COMPONENT,
        MAX_SEGMENTATION_RATIO,
        MIN_SEGMENTATION_RATIO
    )
    from utils.segmentation_validator import validate_and_clean

# Load environment variables
load_dotenv()

# Configuration
IMAGE_SERVER_URL = os.getenv('IMAGE_SERVER', 'http://localhost:8888')
VISTA3D_SERVER = os.getenv('VISTA3D_SERVER', 'http://localhost:8000')
VISTA3D_INFERENCE_URL = f"{VISTA3D_SERVER.rstrip('/')}/v1/vista3d/inference"

# For Vista3D server communication, use the URL that Vista3D container can access
# Vista3D server runs in separate container and needs to access the host machine
# When Vista3D is in Docker and image server is on host, use host.docker.internal
# When both are local, use localhost
# Check if we're running in Docker by looking for container environment
# if os.getenv('DOCKER_CONTAINER') == 'true' or os.path.exists('/.dockerenv'):
#     # We're in Docker, but Vista3D server needs to access host machine
#     # Use environment variable or fallback to host.docker.internal
#     DEFAULT_IMAGE_SERVER_URL = os.getenv('VISTA3D_IMAGE_SERVER_URL', 'http://host.docker.internal:8888')
# else:
#     # We're running locally, both servers are local - use localhost
#     DEFAULT_IMAGE_SERVER_URL = os.getenv('VISTA3D_IMAGE_SERVER_URL', 'http://localhost:8888')

VISTA3D_IMAGE_SERVER_URL = os.getenv('VISTA3D_IMAGE_SERVER_URL', VISTA3D_INFERENCE_URL)
# Use full paths from .env - no more PROJECT_ROOT needed
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER')
if not OUTPUT_FOLDER:
    raise ValueError("OUTPUT_FOLDER must be set in .env file with full path")
NIFTI_INPUT_BASE_DIR = Path(OUTPUT_FOLDER)
PATIENT_OUTPUT_BASE_DIR = Path(OUTPUT_FOLDER)

# Image server configuration (local by default)
# Use IMAGE_SERVER only; external URL env is no longer used

# Get project root for config directory - use the directory containing this script
script_dir = Path(__file__).parent
project_root = script_dir.parent
config_manager = ConfigManager(config_dir=str(project_root / "conf"))
label_colors_list = config_manager.label_colors
LABEL_DICT = {item['id']: item for item in label_colors_list}
NAME_TO_ID_MAP = {item['name']: item['id'] for item in label_colors_list}



def get_nifti_files_in_folder(folder_path: Path):
    """Scans a specific folder for NIfTI files and returns their absolute paths, filtering by minimum file size."""
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    
    nifti_files = []
    filtered_count = 0
    
    for f in os.listdir(folder_path):
        if f.endswith(('.nii', '.nii.gz')):
            file_path = folder_path / f
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if file_size_mb >= MIN_FILE_SIZE_MB:
                nifti_files.append(file_path)
            else:
                filtered_count += 1
                print(f"    Skipping small file: {f} ({file_size_mb:.2f} MB < {MIN_FILE_SIZE_MB} MB)")
    
    if filtered_count > 0:
        print(f"    Filtered out {filtered_count} files smaller than {MIN_FILE_SIZE_MB} MB")
    
    return nifti_files

def create_patient_folder_structure(patient_id: str):
    """Create the new folder structure for a patient."""
    patient_base_dir = PATIENT_OUTPUT_BASE_DIR / patient_id
    nifti_dir = patient_base_dir / "nifti"
    voxels_dir = patient_base_dir / "voxels"
    
    # Create all directories
    nifti_dir.mkdir(parents=True, exist_ok=True)
    voxels_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        'base': patient_base_dir,
        'nifti': nifti_dir,
        'voxels': voxels_dir
    }

def generate_validation_report(
    validation_results: List[Dict[str, Any]],
    patient_id: str,
    scan_name: str,
    nifti_file_path: Path,
    validation_config: Dict[str, Any]
) -> str:
    """
    Generate a comprehensive markdown validation report.
    
    Args:
        validation_results: List of validation result dictionaries
        patient_id: Patient identifier
        scan_name: Name of the scan
        nifti_file_path: Path to the input NIfTI file
        validation_config: Validation configuration used
        
    Returns:
        Markdown formatted report string
    """
    from datetime import datetime
    
    report_lines = []
    report_lines.append("# Segmentation Validation Report")
    report_lines.append("")
    report_lines.append(f"**Patient ID:** {patient_id}")
    report_lines.append(f"**Scan:** {scan_name}")
    report_lines.append(f"**Input File:** {nifti_file_path.name}")
    report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    # Get the most recent validation result (or aggregate if multiple)
    if validation_results:
        result = validation_results[-1]  # Use most recent result
        
        # Overall Status
        report_lines.append("## Overall Status")
        report_lines.append("")
        if result['valid'] and not result['warnings']:
            report_lines.append("✅ **PASSED** - No issues detected")
        elif result['valid']:
            report_lines.append(f"⚠️ **PASSED WITH WARNINGS** - {len(result['warnings'])} warning(s) found")
        else:
            report_lines.append(f"❌ **FAILED** - {len(result['errors'])} error(s) found")
        report_lines.append("")
        
        # Statistics
        stats = result['stats']
        report_lines.append("## Statistics")
        report_lines.append("")
        report_lines.append("| Metric | Value |")
        report_lines.append("|--------|-------|")
        report_lines.append(f"| Total Voxels | {stats.get('total_voxels', 0):,} |")
        report_lines.append(f"| Segmented Voxels | {stats.get('segmented_voxels', 0):,} |")
        report_lines.append(f"| Segmentation Ratio | {stats.get('segmentation_ratio', 0):.2%} |")
        report_lines.append(f"| Number of Labels | {stats.get('num_labels', 0)} |")
        
        if 'label_ids' in stats and stats['label_ids']:
            label_list = ', '.join([str(lid) for lid in stats['label_ids'][:20]])
            if len(stats['label_ids']) > 20:
                label_list += f" ... (and {len(stats['label_ids']) - 20} more)"
            report_lines.append(f"| Label IDs | {label_list} |")
        
        if result['cleaned']:
            report_lines.append("")
            report_lines.append("### Cleanup Statistics")
            report_lines.append("")
            report_lines.append("| Operation | Count |")
            report_lines.append("|-----------|-------|")
            if 'components_removed' in stats:
                report_lines.append(f"| Small Components Removed | {stats['components_removed']} |")
            if 'artifacts_removed' in stats:
                report_lines.append(f"| Artifact Voxels Removed | {stats['artifacts_removed']} |")
        
        report_lines.append("")
        
        # Errors
        if result['errors']:
            report_lines.append("## Errors")
            report_lines.append("")
            for i, error in enumerate(result['errors'], 1):
                report_lines.append(f"{i}. ❌ {error}")
            report_lines.append("")
        
        # Warnings
        if result['warnings']:
            report_lines.append("## Warnings")
            report_lines.append("")
            for i, warning in enumerate(result['warnings'], 1):
                report_lines.append(f"{i}. ⚠️ {warning}")
            report_lines.append("")
        
        # Validation Configuration
        report_lines.append("## Validation Configuration")
        report_lines.append("")
        report_lines.append("| Setting | Value |")
        report_lines.append("|---------|-------|")
        report_lines.append(f"| Validation Enabled | {validation_config.get('enable_validation', 'N/A')} |")
        report_lines.append(f"| Cleanup Enabled | {validation_config.get('enable_cleanup', 'N/A')} |")
        report_lines.append(f"| Min Voxels per Label | {validation_config.get('min_voxels_per_label', 'N/A')} |")
        report_lines.append(f"| Min Voxels per Component | {validation_config.get('min_voxels_per_component', 'N/A')} |")
        report_lines.append(f"| Max Segmentation Ratio | {validation_config.get('max_segmentation_ratio', 'N/A')} |")
        report_lines.append(f"| Min Segmentation Ratio | {validation_config.get('min_segmentation_ratio', 'N/A')} |")
        report_lines.append("")
        
        # Label Details
        if 'label_ids' in stats and stats['label_ids']:
            report_lines.append("## Label Details")
            report_lines.append("")
            report_lines.append("| Label ID | Label Name | Status |")
            report_lines.append("|----------|-----------|--------|")
            
            for label_id in stats['label_ids']:
                label_info = LABEL_DICT.get(label_id, {})
                label_name = label_info.get('name', f'Unknown (ID: {label_id})')
                
                # Check if this label has warnings
                label_warnings = [w for w in result['warnings'] if f'ID: {label_id}' in w or label_name in w]
                if label_warnings:
                    status = f"⚠️ {len(label_warnings)} warning(s)"
                else:
                    status = "✅ OK"
                
                report_lines.append(f"| {label_id} | {label_name} | {status} |")
            report_lines.append("")
        
        # Recommendations
        report_lines.append("## Recommendations")
        report_lines.append("")
        
        recommendations = []
        
        if result['errors']:
            recommendations.append("- **Review errors immediately** - Critical issues detected that may affect segmentation quality")
        
        if len(result['warnings']) > 5:
            recommendations.append("- **Multiple warnings detected** - Consider reviewing segmentation parameters or input image quality")
        
        if stats.get('segmentation_ratio', 0) > 0.9:
            recommendations.append("- **High segmentation ratio** - Segmentation covers most of the volume. Verify this is expected for your use case.")
        
        if stats.get('segmentation_ratio', 0) < 0.01:
            recommendations.append("- **Low segmentation ratio** - Segmentation covers very little of the volume. Consider checking if target structures are present in the image.")
        
        if stats.get('num_labels', 0) == 0:
            recommendations.append("- **No labels found** - Segmentation appears empty. Check if segmentation completed successfully.")
        
        if result['cleaned']:
            recommendations.append("- **Cleanup was applied** - Review cleaned segmentation to ensure valid structures were not removed")
        
        if not recommendations:
            recommendations.append("- **No issues detected** - Segmentation quality appears good")
        
        for rec in recommendations:
            report_lines.append(rec)
        report_lines.append("")
        
        # Footer
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("*This report was automatically generated by the Vista-3D segmentation validation system.*")
        report_lines.append("")
        report_lines.append("*For more information about validation settings and configuration, see the documentation in the project's docs folder.*")
    
    return "\n".join(report_lines)


def create_individual_voxel_files(segmentation_img, ct_scan_name: str, voxels_base_dir: Path, target_vessel_ids: list):
    """Create individual voxel files for each label in the segmentation."""
    # Create folder for this CT scan's voxels
    ct_scan_folder_name = ct_scan_name.replace('.nii.gz', '').replace('.nii', '')
    ct_voxels_dir = voxels_base_dir / ct_scan_folder_name
    ct_voxels_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the segmentation data
    data = segmentation_img.get_fdata().astype(np.int16)
    affine = segmentation_img.affine
    header = segmentation_img.header
    
    # Find unique labels in the segmentation (excluding background/0)
    unique_labels = np.unique(data)
    unique_labels = unique_labels[unique_labels != 0]  # Remove background
    
    print(f"    Found {len(unique_labels)} unique labels in segmentation: {unique_labels}")
    
    created_files = []
    
    # Create individual voxel files for each label
    for label_id in unique_labels:
        if label_id in LABEL_DICT:
            label_info = LABEL_DICT[label_id]
            label_name = label_info['name'].lower().replace(' ', '_').replace('-', '_')
            
            # Create binary mask for this label
            label_data = np.zeros_like(data, dtype=np.int16)
            label_data[data == label_id] = label_id
            
            # Only create file if there are voxels for this label
            if np.any(label_data > 0):
                # Create new NIfTI image for this label
                label_img = nib.Nifti1Image(label_data, affine, header)
                
                # Save individual voxel file
                voxel_filename = f"{label_name}.nii.gz"
                voxel_path = ct_voxels_dir / voxel_filename
                nib.save(label_img, voxel_path)
                
                voxel_count = np.sum(label_data > 0)
                print(f"      Created {voxel_filename} with {voxel_count} voxels (label ID: {label_id})")
                created_files.append(voxel_filename)
    
    print(f"    Created {len(created_files)} individual voxel files in {ct_voxels_dir}")
    return created_files

def main():
    parser = argparse.ArgumentParser(description="Vista3D Batch Segmentation Script")
    parser.add_argument("patient_folders", type=str, nargs='*', default=None, help="Name(s) of the patient folder(s) to process.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing segmentation files.")
    args = parser.parse_args()

    # Create output directories if they don't exist
    NIFTI_INPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    PATIENT_OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

    patient_folders_to_process = []
    if args.patient_folders:
        # Validate that all specified patient folders exist
        for patient_folder in args.patient_folders:
            if (NIFTI_INPUT_BASE_DIR / patient_folder).is_dir():
                patient_folders_to_process.append(patient_folder)
            else:
                print(f"Error: Specified patient folder not found: {NIFTI_INPUT_BASE_DIR / patient_folder}")
                return
    else:
        patient_folders_to_process = [f.name for f in NIFTI_INPUT_BASE_DIR.iterdir() if f.is_dir()]

    if not patient_folders_to_process:
        print("No patient folders found to process. Exiting.")
        return

    print("--- Vista3D Batch Segmentation Script ---")

    for patient_folder_name in tqdm(patient_folders_to_process, desc="Processing patients"):
        # Track validation results for this patient to generate report
        patient_validation_results = []
        # The patient folder is now the base for nifti, scans, etc.
        patient_base_path = NIFTI_INPUT_BASE_DIR / patient_folder_name
        patient_nifti_path = patient_base_path / "nifti"
        print(f"\nProcessing patient folder: {patient_base_path}")

        vessels_of_interest_env = os.getenv('VESSELS_OF_INTEREST', '').strip().lower()
        label_set_name = os.getenv('LABEL_SET', '').strip()
        target_vessels = []
        if label_set_name:
            try:
                label_sets = config_manager.label_sets
                target_vessels = label_sets.get(label_set_name, [])
            except Exception:
                target_vessels = []
        if not target_vessels:
            target_vessels = [v.strip() for v in vessels_of_interest_env.split(',') if v.strip()] if vessels_of_interest_env != "all" else list(NAME_TO_ID_MAP.keys())
        
        if not target_vessels:
            print("No VESSELS_OF_INTEREST specified in .env. Skipping patient.")
            continue

        target_vessel_ids = []
        for v in target_vessels:
            name_key = v
            # Ensure exact match with case and spacing as in config
            if name_key in NAME_TO_ID_MAP:
                target_vessel_ids.append(NAME_TO_ID_MAP[name_key])
        
        # Create folder structure (will ensure nifti and voxels directories exist)
        print(f"  Ensuring folder structure for patient: {patient_folder_name}")
        patient_dirs = create_patient_folder_structure(patient_folder_name)
        print(f"  Patient directories ensured: {patient_dirs['base']}")

        all_nifti_files = get_nifti_files_in_folder(patient_nifti_path)
        
        # Filter files by selected scans if specified
        selected_scans_env = os.getenv('SELECTED_SCANS', '').strip()
        if selected_scans_env:
            selected_scan_names = [scan.strip() for scan in selected_scans_env.split(',') if scan.strip()]
            if selected_scan_names:
                # Filter nifti files to only include selected scans
                filtered_nifti_files = []
                for nifti_file in all_nifti_files:
                    # Get the base name without extension
                    base_name = nifti_file.stem.replace('.nii', '')
                    if base_name in selected_scan_names:
                        filtered_nifti_files.append(nifti_file)
                all_nifti_files = filtered_nifti_files
                print(f"  Filtered to {len(all_nifti_files)} selected scans: {selected_scan_names}")
        
        if not all_nifti_files:
            # Also check if the 'nifti' folder itself is missing
            if not patient_nifti_path.exists():
                print(f"No 'nifti' directory found in {patient_base_path}. Skipping patient.")
            else:
                print(f"No NIfTI files found in {patient_nifti_path}. Skipping patient.")
            continue

        for nifti_file_path in tqdm(all_nifti_files, desc="Processing NIfTI files"):
            # The NIfTI file is already in its final destination.
            # The copy step is no longer needed.
            
            # Define segmentation output path in voxels directory:
            # Save into per-scan folder as 'all.nii.gz'
            ct_scan_folder_name = nifti_file_path.name.replace('.nii.gz', '').replace('.nii', '')
            ct_voxels_dir = patient_dirs['voxels'] / ct_scan_folder_name
            ct_voxels_dir.mkdir(parents=True, exist_ok=True)
            segmentation_output_path = ct_voxels_dir / 'all.nii.gz'

            if not args.force and segmentation_output_path.exists():
                print(f"\n  Skipping {nifti_file_path.name} as segmentation already exists. Use --force to overwrite.")
                continue

            try:
                # Use the original nifti file path for inference
                # Calculate relative path from output folder to the nifti file
                relative_path_to_nifti = nifti_file_path.relative_to(NIFTI_INPUT_BASE_DIR)
                
                # Build URL using Vista3D-accessible image server configuration
                # Vista3D server needs the full path including /output/ prefix
                vista3d_input_url = f"{VISTA3D_IMAGE_SERVER_URL.rstrip('/')}/output/{relative_path_to_nifti}"
                # Read API Key from environment
                api_key = os.getenv('VISTA3D_API_KEY')

                    
                payload = {"image": vista3d_input_url, "prompts": {"labels": target_vessels}}
                headers = {"Content-Type": "application/json"}
                # Update headers to include the Authorization token if the key exists
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                print(f"\n  Processing: {nifti_file_path.name}")
                print(f"    Vista3D Server: {VISTA3D_SERVER}")
                print(f"    Image URL (Vista3D-accessible): {vista3d_input_url}")
                print(f"    Target vessels: {target_vessels}")
                if api_key:
                    print("    Using API Key for authentication.")


                inference_response = requests.post(VISTA3D_INFERENCE_URL, json=payload, headers=headers, verify=False)
                
                # Add detailed error information
                if not inference_response.ok:
                    print(f"    ❌ API Error: {inference_response.status_code} {inference_response.reason}")
                    try:
                        error_detail = inference_response.json()
                        print(f"    Error details: {error_detail}")
                    except:
                        print(f"    Response content: {inference_response.text}")
                
                inference_response.raise_for_status()

                with zipfile.ZipFile(io.BytesIO(inference_response.content), 'r') as zip_ref:
                    nifti_filename = zip_ref.namelist()[0]
                    extracted_nifti_content = zip_ref.read(nifti_filename)
                
                # Create a temporary file to load the NIfTI image, as nibabel.load
                # can have issues with in-memory BytesIO objects.
                raw_nifti_img = None
                tmp_path = None
                try:
                    # The '.nii.gz' suffix is important for nibabel to correctly decompress.
                    with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as tmp:
                        tmp.write(extracted_nifti_content)
                        tmp_path = tmp.name

                    # Load the NIfTI image from the temporary file.
                    img_loaded = nib.load(tmp_path)
                    
                    # Immediately load the data into memory to prevent issues with the temp file.
                    # Get data as float, then explicitly convert to int16
                    float_data = img_loaded.get_fdata(dtype=np.float32)
                    data = np.zeros(float_data.shape, dtype=np.int16)
                    data[:] = float_data[:]
                    data = np.ascontiguousarray(data) # Ensure contiguous
                    print(f"    Shape of data array: {data.shape}")
                    affine = img_loaded.affine
                    
                    # Create a new NIfTI header to ensure 3D dimensions
                    new_header = nib.Nifti1Header()
                    new_header.set_data_shape(data.shape)
                    new_header.set_data_dtype(np.int16) # Set dtype based on the numpy array
                    
                    # Create a new NIfTI image object in memory with the new header.
                    raw_nifti_img = nib.Nifti1Image(data, affine, new_header)

                except Exception as load_error:
                    import traceback
                    print(f"    ❌ Error loading NIfTI file with nibabel: {load_error}")
                    print("    Full traceback for nibabel.load error:")
                    traceback.print_exc()
                    raise  # Re-raise the exception
                finally:
                    # Clean up the temporary file.
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)

                # After loading, check if the image object was created successfully
                if raw_nifti_img is None:
                    raise Exception("Failed to load NIfTI image from received content.")
                
                print(f"    Data type of raw_nifti_img data: {raw_nifti_img.get_fdata().dtype}")
                print(f"    NIfTI header datatype: {raw_nifti_img.header['datatype']}")
                
                # Prepare validation config (needed for report generation)
                validation_config = {
                    'enable_cleanup': ENABLE_SEGMENTATION_CLEANUP,
                    'min_voxels_per_label': MIN_VOXELS_PER_LABEL,
                    'min_voxels_per_component': MIN_VOXELS_PER_COMPONENT,
                    'max_segmentation_ratio': MAX_SEGMENTATION_RATIO,
                    'min_segmentation_ratio': MIN_SEGMENTATION_RATIO
                }
                
                # Validate and optionally clean segmentation
                if ENABLE_SEGMENTATION_VALIDATION:
                    print(f"    Running segmentation validation...")
                    try:
                        # Load input image for comparison (only if validation enabled)
                        input_img = None
                        if nifti_file_path.exists():
                            input_img = nib.load(str(nifti_file_path))
                        
                        # Run validation
                        validation_result = validate_and_clean(
                            raw_nifti_img,
                            input_img,
                            LABEL_DICT,
                            validation_config
                        )
                        
                        # Store validation result for report generation
                        validation_result['scan_name'] = ct_scan_folder_name
                        validation_result['nifti_file'] = nifti_file_path.name
                        patient_validation_results.append(validation_result)
                        
                        # Log validation results
                        if validation_result['errors']:
                            print(f"    ⚠️  Validation Errors:")
                            for error in validation_result['errors']:
                                print(f"      ❌ {error}")
                        
                        if validation_result['warnings']:
                            print(f"    ⚠️  Validation Warnings ({len(validation_result['warnings'])}):")
                            for warning in validation_result['warnings'][:5]:  # Show first 5 warnings
                                print(f"      ⚠️  {warning}")
                            if len(validation_result['warnings']) > 5:
                                print(f"      ... and {len(validation_result['warnings']) - 5} more warning(s)")
                        
                        # Log statistics
                        stats = validation_result['stats']
                        print(f"    Validation Statistics:")
                        print(f"      Labels found: {stats.get('num_labels', 0)}")
                        print(f"      Segmented voxels: {stats.get('segmented_voxels', 0):,}")
                        print(f"      Segmentation ratio: {stats.get('segmentation_ratio', 0):.2%}")
                        
                        if validation_result['cleaned']:
                            print(f"    ✅ Cleanup applied:")
                            if 'components_removed' in stats:
                                print(f"      Removed {stats['components_removed']} small component(s)")
                            if 'artifacts_removed' in stats:
                                print(f"      Removed {stats['artifacts_removed']} artifact voxel(s)")
                            # Use cleaned image
                            raw_nifti_img = validation_result['cleaned_img']
                        
                        if validation_result['valid'] and not validation_result['warnings']:
                            print(f"    ✅ Validation passed with no issues")
                        elif validation_result['valid']:
                            print(f"    ⚠️  Validation passed with warnings")
                        else:
                            print(f"    ❌ Validation failed with errors (continuing anyway)")
                    
                    except Exception as validation_error:
                        print(f"    ⚠️  Validation error (continuing): {validation_error}")
                        import traceback
                        traceback.print_exc()
                
                # Save full segmentation to voxels folder
                nib.save(raw_nifti_img, segmentation_output_path)
                print(f"    Successfully saved segmentation: {segmentation_output_path.name}")
                
                # Create individual voxel files
                print(f"    Creating individual voxel files...")
                created_voxels = create_individual_voxel_files(
                    raw_nifti_img, 
                    nifti_file_path.name, 
                    patient_dirs['voxels'], 
                    target_vessel_ids
                )
                print(f"    Created {len(created_voxels)} individual voxel files")

            except requests.exceptions.RequestException as e:
                print(f"\n  Error during inference for {nifti_file_path.name}: {e}")
            except Exception as e:
                print(f"\n  An unexpected error occurred for {nifti_file_path.name}: {e}")
        
        # Generate and save validation report for this patient
        if ENABLE_SEGMENTATION_VALIDATION and patient_validation_results:
            try:
                # Use the most recent validation result for the report
                # (or could aggregate all results for a comprehensive patient-level report)
                latest_result = patient_validation_results[-1]
                scan_name = latest_result.get('scan_name', 'unknown')
                nifti_file = latest_result.get('nifti_file', 'unknown')
                
                # Find the corresponding nifti file path
                report_nifti_path = patient_nifti_path / nifti_file
                if not report_nifti_path.exists():
                    # Try to find any nifti file in the folder
                    nifti_files = list(patient_nifti_path.glob('*.nii*'))
                    if nifti_files:
                        report_nifti_path = nifti_files[0]
                
                # Prepare validation config for report (recreate if needed)
                validation_config_for_report = {
                    'enable_validation': ENABLE_SEGMENTATION_VALIDATION,
                    'enable_cleanup': ENABLE_SEGMENTATION_CLEANUP,
                    'min_voxels_per_label': MIN_VOXELS_PER_LABEL,
                    'min_voxels_per_component': MIN_VOXELS_PER_COMPONENT,
                    'max_segmentation_ratio': MAX_SEGMENTATION_RATIO,
                    'min_segmentation_ratio': MIN_SEGMENTATION_RATIO
                }
                
                report_content = generate_validation_report(
                    patient_validation_results,
                    patient_folder_name,
                    scan_name,
                    report_nifti_path,
                    validation_config_for_report
                )
                
                # Save report to patient nifti folder
                report_path = patient_nifti_path / "segment_validation.md"
                report_path.write_text(report_content, encoding='utf-8')
                print(f"\n  ✅ Saved validation report: {report_path}")
                
            except Exception as report_error:
                print(f"\n  ⚠️  Error generating validation report: {report_error}")
                import traceback
                traceback.print_exc()

    print("\n--- Segmentation Process Complete ---")

if __name__ == "__main__":
    main()