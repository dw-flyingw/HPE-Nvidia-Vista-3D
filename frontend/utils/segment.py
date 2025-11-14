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
from dotenv import load_dotenv
try:
    from utils.config_manager import ConfigManager
    from utils.constants import MIN_FILE_SIZE_MB
except ModuleNotFoundError:
    # Allow running as a script: python utils/segment.py
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parents[1]))
    from utils.config_manager import ConfigManager
    from utils.constants import MIN_FILE_SIZE_MB

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

    print("\n--- Segmentation Process Complete ---")

if __name__ == "__main__":
    main()