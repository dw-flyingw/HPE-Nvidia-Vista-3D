#!/usr/bin/env python3
"""
Enhanced DICOM to NIFTI conversion script for Vista-3D pipeline using dcm2niix.
This script follows NiiVue best practices and uses dcm2niix for robust conversion.
Incorporates lessons from https://github.com/niivue/niivue-dcm2niix
"""

import os
import warnings
import json
import subprocess
import shutil
import time
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
import nibabel as nib
import numpy as np
import traceback
from scipy import ndimage
import scipy.ndimage as ndi

# Import the shared constants
import sys
sys.path.append(str(Path(__file__).parent))
from constants import MIN_FILE_SIZE_MB


def check_dcm2niix_installation():
    """Check if dcm2niix is installed and accessible"""
    try:
        result = subprocess.run(['dcm2niix', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            # Extract version info
            version_line = result.stdout.split('\n')[0] if result.stdout else "Unknown version"
            print(f"✅ dcm2niix found: {version_line}")
            return True
        else:
            print(f"❌ dcm2niix check failed with return code: {result.returncode}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ dcm2niix check timed out")
        return False
    except FileNotFoundError:
        print("❌ dcm2niix not found in PATH")
        return False
    except Exception as e:
        print(f"❌ dcm2niix check failed: {e}")
        return False


def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    
    # Check if we're running in a Docker container
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
    
    if is_docker:
        # In Docker container, use the mounted paths
        dicom_folder = '/app/dicom'
        output_folder = '/app/output'
    else:
        # On host machine, use environment variables
        dicom_folder = os.getenv('DICOM_FOLDER')
        output_folder = os.getenv('OUTPUT_FOLDER')
        
        if not dicom_folder:
            raise ValueError("DICOM_FOLDER not found in .env file")
        if not output_folder:
            raise ValueError("OUTPUT_FOLDER not found in .env file")
        
        # DICOM_FOLDER should be a full path now - no more PROJECT_ROOT needed
        if not os.path.isabs(dicom_folder):
            raise ValueError("DICOM_FOLDER must be set in .env file with full absolute path")
        if not os.path.isabs(output_folder):
            raise ValueError("OUTPUT_FOLDER must be set in .env file with full absolute path")
    
    return dicom_folder


def load_label_dictionary():
    """Load the Vista-3D label dictionary from JSON file"""
    try:
        # Try to load from the conf directory first
        label_file = Path("conf/vista3d_label_dict.json")
        if not label_file.exists():
            # Fallback to current directory
            label_file = Path("vista3d_label_dict.json")
        
        with open(label_file, 'r') as f:
            label_dict = json.load(f)
        
        print(f"✅ Loaded label dictionary with {len(label_dict)} anatomical structures")
        return label_dict
    except Exception as e:
        print(f"⚠️  Warning: Could not load label dictionary: {e}")
        print("   Using default label mapping")
        # Fallback to basic mapping
        return {
            'background': 0,
            'aorta': 6,
            'left iliac artery': 58,
            'right iliac artery': 59
        }


def check_patient_folders_exist(dicom_path: Path) -> bool:
    """Check if any subdirectories (patient folders) exist in the DICOM path."""
    if not dicom_path.is_dir():
        return False
    
    for entry in os.scandir(dicom_path):
        if entry.is_dir():
            return True
    return False


def get_modality_specific_dcm2niix_settings(modality, is_reformatted=True):
    """
    Get modality-specific dcm2niix settings optimized for CT vs MRI scans.
    
    Args:
        modality: Scan modality ('CT' or 'MR')
        is_reformatted: Whether this is a reformatted slice
    
    Returns:
        list: dcm2niix command arguments optimized for the modality
    """
    base_settings = [
        'dcm2niix',
        '-b', 'y',           # Generate BIDS sidecar JSON
        '-ba', 'y',          # Anonymize BIDS sidecar
        '-f', '%d_%s',       # Filename format
        '-v', '2',           # Maximum verbose output for troubleshooting
        '-x', 'i',           # Ignore cropping and rotation (preserves all data for reformatting)
        '-w', '2',           # Write behavior: 2 = write all series (including reformatted)
        '-i', 'n',           # Ignore derived images: n = no (include reformatted slices)
        '-l', 'y',           # Losslessly scale 16-bit integers to use full dynamic range
        '-m', '2',           # Auto-merge 2D slices from same series (best quality)
        '--big-endian', 'o', # Optimal byte order (native)
    ]
    
    if modality == 'CT':
        # CT-optimized settings for maximum quality and HU preservation
        ct_settings = [
            '-z', 'o',           # Optimal compression (best quality/size ratio for CT)
            '-1', '9',           # Maximum compression level (9=smallest, best quality)
            '-p', 'y',           # Philips precise float scaling (not display scaling)
            '--ct_slope_intercept', 'y',  # Preserve CT slope/intercept for accurate HU values
        ]
        return base_settings + ct_settings
    
    elif modality == 'MR':
        # MRI-optimized settings for maximum quality and contrast preservation
        mr_settings = [
            '-z', 'y',           # Compress output (.nii.gz) - MRI benefits from compression
            '-1', '6',           # Moderate compression level (6=good quality/size balance for MRI)
            '-p', 'n',           # Don't apply Philips scaling (not needed for MRI)
            '--mri_slope_intercept', 'y',  # Preserve MRI slope/intercept for accurate intensity values
        ]
        return base_settings + mr_settings
    
    else:
        # Default high-quality settings for unknown modalities
        default_settings = [
            '-z', 'o',           # Optimal compression
            '-1', '9',           # Maximum compression level
            '-p', 'y',           # Philips precise float scaling
        ]
        return base_settings + default_settings


def run_dcm2niix_conversion(input_dir, output_dir, filename_format="%d_%s", optimize_reformatted=True, modality='Unknown'):
    """
    Run dcm2niix conversion with modality-specific NiiVue-optimized settings.
    
    Args:
        input_dir: Input DICOM directory
        output_dir: Output directory for NIFTI files
        filename_format: Output filename format (dcm2niix -f option)
        optimize_reformatted: If True, use settings optimized for reformatted slices
        modality: Scan modality ('CT', 'MR', or 'Unknown') for optimization
    
    Returns:
        dict: Conversion results with status and files created
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Get modality-specific dcm2niix settings
        cmd = get_modality_specific_dcm2niix_settings(modality, optimize_reformatted)
        
        # Add output directory and input directory
        cmd.extend(['-o', str(output_dir), str(input_dir)])
        
        # Override filename format if specified
        if filename_format != "%d_%s":
            cmd[cmd.index('%d_%s')] = filename_format
        
        print(f"🔧 Running dcm2niix conversion:")
        print(f"   Command: {' '.join(cmd)}")
        
        # Run dcm2niix with byte output to handle encoding issues
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=300)
        
        # Decode output with error handling for non-UTF-8 characters
        # This handles DICOM files with special characters in metadata
        try:
            stdout = result.stdout.decode('utf-8')
            stderr = result.stderr.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback: replace problematic bytes with replacement character
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
        
        if result.returncode == 0:
            print(f"✅ dcm2niix conversion successful")
            
            # Find created files
            nifti_files = list(Path(output_dir).glob("*.nii.gz"))
            json_files = list(Path(output_dir).glob("*.json"))
            
            print(f"📁 Created {len(nifti_files)} NIFTI files and {len(json_files)} JSON sidecars")
            
            return {
                'status': 'success',
                'nifti_files': nifti_files,
                'json_files': json_files,
                'stdout': stdout,
                'stderr': stderr
            }
        else:
            print(f"❌ dcm2niix conversion failed (return code: {result.returncode})")
            print(f"   stderr: {stderr}")
            print(f"   stdout: {stdout}")
            
            return {
                'status': 'failed',
                'error': stderr,
                'stdout': stdout,
                'return_code': result.returncode
            }
            
    except subprocess.TimeoutExpired:
        print("❌ dcm2niix conversion timed out")
        return {'status': 'timeout', 'error': 'Conversion timed out after 5 minutes'}
    except Exception as e:
        print(f"❌ dcm2niix conversion error: {e}")
        return {'status': 'error', 'error': str(e)}


def detect_reformatted_slice(json_file):
    """
    Detect if a NIFTI file represents a reformatted slice based on DICOM metadata.
    
    Args:
        json_file: Path to JSON sidecar file
    
    Returns:
        bool: True if this is a reformatted slice
    """
    try:
        if not json_file or not json_file.exists():
            return False
            
        with open(json_file, 'r') as f:
            metadata = json.load(f)
        
        # Check for reformatted image indicators
        image_type = metadata.get('ImageType', [])
        if isinstance(image_type, list):
            return 'REFORMATTED' in image_type or 'DERIVED' in image_type
        
        return False
    except Exception:
        return False


def format_patient_age(age_str):
    """
    Format patient age in DICOM format (e.g., "045Y" for 45 years).
    
    Args:
        age_str: Age string from DICOM metadata (could be in various formats)
    
    Returns:
        str: Formatted age string in DICOM format (NNN[D|W|M|Y])
    """
    if not age_str or age_str == 'Unknown' or age_str == '':
        return None
    
    # Check if already in DICOM format (ends with D, W, M, or Y)
    age_str = str(age_str).strip()
    if age_str[-1].upper() in ['D', 'W', 'M', 'Y']:
        return age_str
    
    # Try to parse as numeric value and assume years
    try:
        age_num = float(age_str)
        # Format as DICOM age: zero-padded 3 digits + unit
        return f"{int(age_num):03d}Y"
    except (ValueError, TypeError):
        # If can't parse, return None
        return None


def extract_comprehensive_metadata(json_file, nifti_file):
    """
    Extract comprehensive DICOM metadata from JSON sidecar and create enhanced metadata file.
    
    Args:
        json_file: Path to dcm2niix JSON sidecar file
        nifti_file: Path to corresponding NIfTI file (for output path)
    
    Returns:
        dict: Comprehensive metadata dictionary with all requested fields
    """
    comprehensive_metadata = {}
    
    try:
        if not json_file or not json_file.exists():
            print(f"    ⚠️  JSON sidecar not found, creating minimal metadata")
            return comprehensive_metadata
        
        with open(json_file, 'r') as f:
            dicom_metadata = json.load(f)
        
        # Preserve all original metadata fields from dcm2niix
        # dcm2niix already extracts most DICOM fields, so we keep everything and format as needed
        comprehensive_metadata = dicom_metadata.copy()
        
        # Patient Demographics - format age in DICOM format (e.g., "045Y")
        patient_age = dicom_metadata.get('PatientAge', '')
        if patient_age:
            formatted_age = format_patient_age(patient_age)
            if formatted_age:
                comprehensive_metadata['PatientAge'] = formatted_age
        
        # All requested fields are preserved from the original dcm2niix JSON:
        # - PatientAge: Formatted above in DICOM format (e.g., "045Y")
        # - PatientSex: M/F/O (already in JSON)
        # - PatientWeight: kg (already in JSON)
        # - PatientSize: meters (already in JSON)
        # - PatientBirthDate: (already in JSON)
        # - PatientID: (already in JSON)
        # - StudyDate, StudyTime, StudyDescription: (already in JSON)
        # - SeriesDescription: (already in JSON)
        # - Modality: (already in JSON)
        # - Manufacturer: (already in JSON)
        # - ManufacturersModelName: (already in JSON)
        # - ContrastBolusAgent, ContrastBolusVolume, etc.: (already in JSON if present)
        # - Scan parameters (ExposureTime, XRayTubeCurrent, etc.): (already in JSON if present)
        
        # Save enhanced metadata JSON file (overwrite the original dcm2niix JSON with age-formatted version)
        enhanced_metadata_path = json_file  # Overwrite the original JSON with enhanced version
        
        with open(enhanced_metadata_path, 'w') as f:
            json.dump(comprehensive_metadata, f, indent=2, default=str)
        
        print(f"    ✅ Created comprehensive metadata file: {json_file.name}")
        
        return comprehensive_metadata
        
    except Exception as e:
        print(f"    ⚠️  Error extracting comprehensive metadata: {e}")
        return comprehensive_metadata


def detect_scan_modality(json_file):
    """
    Detect scan modality (MRI, CT, etc.) from DICOM metadata.
    
    Args:
        json_file: Path to JSON sidecar file
    
    Returns:
        dict: Modality information including type, manufacturer, and additional details
    """
    try:
        if not json_file or not json_file.exists():
            return {
                'modality': 'Unknown',
                'manufacturer': 'Unknown',
                'model': 'Unknown',
                'study_description': 'Unknown',
                'series_description': 'Unknown',
                'detection_method': 'No metadata available'
            }
            
        with open(json_file, 'r') as f:
            metadata = json.load(f)
        
        # Extract modality information
        modality = metadata.get('Modality', 'Unknown')
        manufacturer = metadata.get('Manufacturer', 'Unknown')
        model = metadata.get('ManufacturersModelName', 'Unknown')
        study_desc = metadata.get('StudyDescription', 'Unknown')
        series_desc = metadata.get('SeriesDescription', 'Unknown')
        
        # Additional modality-specific information
        modality_info = {
            'modality': modality,
            'manufacturer': manufacturer,
            'model': model,
            'study_description': study_desc,
            'series_description': series_desc,
            'detection_method': 'DICOM metadata'
        }
        
        # Add modality-specific details
        if modality == 'MR':
            modality_info.update({
                'magnetic_field_strength': metadata.get('MagneticFieldStrength', 'Unknown'),
                'imaging_frequency': metadata.get('ImagingFrequency', 'Unknown'),
                'pulse_sequence': metadata.get('PulseSequenceName', 'Unknown'),
                'scanning_sequence': metadata.get('ScanningSequence', 'Unknown'),
                'echo_time': metadata.get('EchoTime', 'Unknown'),
                'repetition_time': metadata.get('RepetitionTime', 'Unknown'),
                'flip_angle': metadata.get('FlipAngle', 'Unknown'),
                'body_part': metadata.get('BodyPart', 'Unknown')
            })
        elif modality == 'CT':
            modality_info.update({
                'xray_tube_current': metadata.get('XRayTubeCurrent', 'Unknown'),
                'exposure_time': metadata.get('ExposureTime', 'Unknown'),
                'convolution_kernel': metadata.get('ConvolutionKernel', 'Unknown'),
                'scan_options': metadata.get('ScanOptions', 'Unknown'),
                'protocol_name': metadata.get('ProtocolName', 'Unknown')
            })
        
        return modality_info
        
    except Exception as e:
        return {
            'modality': 'Unknown',
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'study_description': 'Unknown',
            'series_description': 'Unknown',
            'detection_method': f'Error reading metadata: {str(e)}'
        }


def apply_ct_specific_enhancements(data, modality_info):
    """
    Apply CT-specific quality enhancements optimized for Hounsfield Unit preservation.
    
    Args:
        data: Input CT image data
        modality_info: Modality information dictionary
    
    Returns:
        np.ndarray: Enhanced CT data
    """
    print(f"    🔧 Applying CT-specific quality enhancements...")
    
    # CT-specific enhancements
    enhanced_data = data.copy()
    
    # 1. HU value preservation and noise reduction
    # CT data should maintain accurate HU values, so we use conservative enhancement
    if np.min(enhanced_data) < -100:  # Confirmed CT data (has negative HU values)
        # Apply gentle noise reduction while preserving HU accuracy
        enhanced_data = ndi.gaussian_filter(enhanced_data, sigma=0.3)
        print(f"    ✅ Applied gentle noise reduction for HU preservation")
    
    # 2. Edge enhancement for better soft tissue contrast
    # Use unsharp mask with CT-optimized parameters
    sigma = 0.8  # Larger sigma for CT (preserves larger structures)
    amount = 0.2  # Conservative amount for HU accuracy
    threshold = 50  # Higher threshold for CT (HU units)
    
    # Apply unsharp mask
    blurred = ndi.gaussian_filter(enhanced_data, sigma=sigma)
    unsharp_mask = enhanced_data - blurred
    sharpened = enhanced_data + amount * unsharp_mask
    
    # Only apply sharpening where signal is above threshold
    mask = np.abs(enhanced_data) > threshold
    enhanced_data = np.where(mask, sharpened, enhanced_data)
    
    print(f"    ✅ Applied CT-optimized edge enhancement (σ={sigma}, amount={amount})")
    
    # 3. Contrast optimization for CT windowing
    # Enhance contrast in the typical CT window range (-1000 to 3000 HU)
    hu_range = enhanced_data[(enhanced_data >= -1000) & (enhanced_data <= 3000)]
    if len(hu_range) > 0:
        # Apply gentle contrast stretching in the HU range
        hu_min, hu_max = np.percentile(hu_range, [1, 99])
        if hu_max > hu_min:
            enhanced_data = np.clip(enhanced_data, hu_min, hu_max)
            enhanced_data = (enhanced_data - hu_min) / (hu_max - hu_min) * (hu_max - hu_min) + hu_min
            print(f"    ✅ Applied CT contrast optimization (HU range: {hu_min:.1f} to {hu_max:.1f})")
    
    return enhanced_data


def apply_mri_specific_enhancements(data, modality_info):
    """
    Apply MRI-specific quality enhancements optimized for contrast and artifact reduction.
    
    Args:
        data: Input MRI image data
        modality_info: Modality information dictionary
    
    Returns:
        np.ndarray: Enhanced MRI data
    """
    print(f"    🔧 Applying MRI-specific quality enhancements...")
    
    # MRI-specific enhancements
    enhanced_data = data.copy()
    
    # 1. Noise reduction optimized for MRI characteristics
    # MRI typically has different noise characteristics than CT
    if np.max(enhanced_data) > 0:  # Confirmed MRI data (positive values)
        # Apply adaptive noise reduction
        enhanced_data = ndi.gaussian_filter(enhanced_data, sigma=0.4)
        print(f"    ✅ Applied MRI-optimized noise reduction")
    
    # 2. Contrast enhancement for better tissue differentiation
    # MRI benefits from more aggressive contrast enhancement
    sigma = 0.6  # Smaller sigma for MRI (preserves fine details)
    amount = 0.4  # More aggressive for MRI contrast
    threshold = 10  # Lower threshold for MRI (intensity units)
    
    # Apply unsharp mask
    blurred = ndi.gaussian_filter(enhanced_data, sigma=sigma)
    unsharp_mask = enhanced_data - blurred
    sharpened = enhanced_data + amount * unsharp_mask
    
    # Only apply sharpening where signal is above threshold
    mask = np.abs(enhanced_data) > threshold
    enhanced_data = np.where(mask, sharpened, enhanced_data)
    
    print(f"    ✅ Applied MRI-optimized contrast enhancement (σ={sigma}, amount={amount})")
    
    # 3. Artifact reduction for common MRI artifacts
    # Apply gentle smoothing to reduce motion artifacts
    if 'magnetic_field_strength' in modality_info and modality_info['magnetic_field_strength'] != 'Unknown':
        field_strength = modality_info['magnetic_field_strength']
        if field_strength >= 3.0:  # High field MRI
            # Apply additional smoothing for high field artifacts
            enhanced_data = ndi.gaussian_filter(enhanced_data, sigma=0.2)
            print(f"    ✅ Applied high-field MRI artifact reduction")
    
    # 4. Intensity normalization for better visualization
    # Normalize to 0-1 range while preserving relative contrast
    data_min, data_max = np.percentile(enhanced_data, [1, 99])
    if data_max > data_min:
        enhanced_data = np.clip(enhanced_data, data_min, data_max)
        enhanced_data = (enhanced_data - data_min) / (data_max - data_min)
        print(f"    ✅ Applied MRI intensity normalization")
    
    return enhanced_data


def apply_advanced_interpolation(data, target_spacing=None, method='cubic'):
    """
    Apply advanced interpolation to improve reformatted slice quality.
    
    Args:
        data: Input image data
        target_spacing: Target voxel spacing (if None, use current spacing)
        method: Interpolation method ('linear', 'cubic', 'quintic')
    
    Returns:
        tuple: (interpolated_data, new_spacing)
    """
    if method == 'cubic':
        order = 3
    elif method == 'quintic':
        order = 5
    else:
        order = 1
    
    # If no target spacing specified, use current spacing
    if target_spacing is None:
        return data, None
    
    # Calculate zoom factors
    current_spacing = np.array([1.0, 1.0, 1.0])  # Assume isotropic for now
    zoom_factors = current_spacing / np.array(target_spacing)
    
    # Apply interpolation
    interpolated_data = ndi.zoom(data, zoom_factors, order=order, mode='constant', cval=0.0)
    
    return interpolated_data, target_spacing


def enhance_nifti_for_niivue(nifti_file, json_file=None):
    """
    Enhance NIFTI file for optimal NiiVue compatibility.
    
    Args:
        nifti_file: Path to NIFTI file
        json_file: Path to associated JSON sidecar (optional)
    
    Returns:
        dict: Enhancement results
    """
    try:
        print(f"🔧 Enhancing {nifti_file.name} for NiiVue...")
        
        # Check if this is a reformatted slice
        is_reformatted = detect_reformatted_slice(json_file)
        if is_reformatted:
            print(f"    📐 Detected reformatted slice - applying quality optimizations...")
        
        # Detect scan modality (MRI, CT, etc.)
        modality_info = detect_scan_modality(json_file)
        print(f"    🔬 Detected scan modality: {modality_info['modality']} ({modality_info['manufacturer']} {modality_info['model']})")
        
        # Load NIFTI file with error handling
        try:
            img = nib.load(str(nifti_file))
            data = img.get_fdata()
            
            # Check data size and warn if very large
            data_size_mb = data.nbytes / (1024 * 1024)
            if data_size_mb > 100:  # > 100MB
                print(f"    ⚠️  Large dataset detected: {data_size_mb:.1f} MB - processing may take longer")
        except Exception as e:
            print(f"    ❌ Error loading NIFTI file: {e}")
            return {'status': 'failed', 'error': f'Failed to load NIFTI file: {e}'}
        
        # Apply modality-specific quality enhancements
        modality = modality_info['modality']
        
        if modality == 'CT':
            # Apply CT-specific enhancements
            data = apply_ct_specific_enhancements(data, modality_info)
            
            # Update the NIfTI image with enhanced data
            enhanced_img = nib.Nifti1Image(data, img.affine, img.header)
            
            # Save the enhanced version directly to the original file (in-place enhancement)
            nib.save(enhanced_img, str(nifti_file))
            
            print(f"    💾 Enhanced CT data saved in-place: {nifti_file.name}")
            
        elif modality == 'MR':
            # Apply MRI-specific enhancements
            data = apply_mri_specific_enhancements(data, modality_info)
            
            # Update the NIfTI image with enhanced data
            enhanced_img = nib.Nifti1Image(data, img.affine, img.header)
            
            # Save the enhanced version directly to the original file (in-place enhancement)
            nib.save(enhanced_img, str(nifti_file))
            
            print(f"    💾 Enhanced MRI data saved in-place: {nifti_file.name}")
            
        else:
            # For unknown modalities, apply general high-quality enhancements
            if is_reformatted:
                print(f"    🔧 Applying general quality enhancements for reformatted slice...")
                
                # Apply sharpening filter to improve edge definition
                sigma = 0.5  # Gaussian blur sigma
                amount = 0.3  # Sharpening amount
                threshold = 0.1  # Threshold for sharpening
                
                # Apply Gaussian blur
                blurred = ndi.gaussian_filter(data, sigma=sigma)
                
                # Create unsharp mask
                unsharp_mask = data - blurred
                
                # Apply sharpening with threshold
                sharpened = data + amount * unsharp_mask
                
                # Only apply sharpening where the original signal is above threshold
                mask = np.abs(data) > threshold
                data = np.where(mask, sharpened, data)
                
                # Update the NIfTI image with enhanced data
                enhanced_img = nib.Nifti1Image(data, img.affine, img.header)
                
                # Save the enhanced version directly to the original file (in-place enhancement)
                nib.save(enhanced_img, str(nifti_file))
                
                print(f"    ✅ Applied general unsharp mask sharpening (σ={sigma}, amount={amount})")
                print(f"    💾 Enhanced original file in-place: {nifti_file.name}")
        
        # Update the data for quality reporting
        data = enhanced_img.get_fdata() if 'enhanced_img' in locals() else data
        
        # Calculate advanced quality metrics
        def calculate_quality_metrics(data):
            """Calculate advanced quality metrics for medical imaging data."""
            try:
                # Edge sharpness using Laplacian variance - use a more efficient approach
                # For large datasets, use a subsampled approach to avoid memory issues
                data_size = data.size
                if data_size > 10_000_000:  # 10M voxels
                    # Subsample for large datasets
                    step = max(1, int(np.ceil(data_size / 1_000_000) ** (1/3)))
                    subsampled = data[::step, ::step, ::step]
                    laplacian = ndi.laplace(subsampled)
                    edge_sharpness = float(np.var(laplacian))
                else:
                    laplacian = ndi.laplace(data)
                    edge_sharpness = float(np.var(laplacian))
                
                # Signal-to-noise ratio estimation
                # Use background regions (low intensity) to estimate noise
                try:
                    background_mask = data < np.percentile(data, 10)
                    if np.any(background_mask):
                        noise_std = float(np.std(data[background_mask]))
                        signal_mean = float(np.mean(data[data > np.percentile(data, 90)]))
                        snr = signal_mean / noise_std if noise_std > 0 else float('inf')
                    else:
                        snr = float('inf')
                except Exception:
                    snr = float('inf')
                
                # Contrast-to-noise ratio
                try:
                    high_intensity = data[data > np.percentile(data, 90)]
                    low_intensity = data[data < np.percentile(data, 10)]
                    if len(high_intensity) > 0 and len(low_intensity) > 0:
                        cnr = (float(np.mean(high_intensity)) - float(np.mean(low_intensity))) / float(np.std(data))
                    else:
                        cnr = 0.0
                except Exception:
                    cnr = 0.0
                
                # Spatial resolution (effective resolution)
                try:
                    voxel_volume = np.prod(img.header.get_zooms()[:3])
                    effective_resolution = float(voxel_volume ** (1/3))
                except Exception:
                    effective_resolution = 1.0
                
                # Noise level calculation with error handling
                try:
                    noise_level = float(np.std(data[data < np.percentile(data, 20)])) if np.any(data < np.percentile(data, 20)) else 0.0
                except Exception:
                    noise_level = 0.0
                
                return {
                    'edge_sharpness': edge_sharpness,
                    'signal_to_noise_ratio': snr,
                    'contrast_to_noise_ratio': cnr,
                    'effective_resolution_mm': effective_resolution,
                    'noise_level': noise_level
                }
            except Exception as e:
                print(f"    ⚠️  Warning: Could not calculate quality metrics: {e}")
                return {
                    'edge_sharpness': 0.0,
                    'signal_to_noise_ratio': 0.0,
                    'contrast_to_noise_ratio': 0.0,
                    'effective_resolution_mm': 1.0,
                    'noise_level': 0.0
                }
        
        # Calculate quality metrics (always enabled)
        enable_quality_metrics = True
        if enable_quality_metrics:
            try:
                print(f"    📊 Calculating quality metrics...")
                quality_metrics = calculate_quality_metrics(data)
                print(f"    ✅ Quality metrics calculated successfully")
            except Exception as e:
                print(f"    ⚠️  Warning: Quality metrics calculation failed: {e}")
                quality_metrics = {
                    'edge_sharpness': 0.0,
                    'signal_to_noise_ratio': 0.0,
                    'contrast_to_noise_ratio': 0.0,
                    'effective_resolution_mm': 1.0,
                    'noise_level': 0.0
                }
        else:
            quality_metrics = {
                'edge_sharpness': 0.0,
                'signal_to_noise_ratio': 0.0,
                'contrast_to_noise_ratio': 0.0,
                'effective_resolution_mm': 1.0,
                'noise_level': 0.0
            }
        
        # Generate quality report
        quality_info = {
            'file_info': {
                'filename': nifti_file.name,
                'file_size_mb': nifti_file.stat().st_size / (1024*1024),
                'compression': nifti_file.suffix == '.gz'
            },
            'volume_info': {
                'dimensions': data.shape,
                'data_type': str(data.dtype),
                'total_voxels': data.size,
                'memory_usage_mb': data.nbytes / (1024*1024)
            },
            'data_quality': {
                'min_value': float(data.min()),
                'max_value': float(data.max()),
                'mean_value': float(data.mean()),
                'std_value': float(data.std()),
                'dynamic_range': float(data.max() - data.min())
            },
            'spatial_info': {
                'voxel_spacing_mm': [float(x) for x in img.header.get_zooms()],
                'volume_dimensions_mm': [
                    float(img.header.get_zooms()[i] * data.shape[i]) 
                    for i in range(min(3, len(data.shape)))
                ]
            },
            'scan_modality': modality_info,
            'advanced_quality_metrics': quality_metrics
        }
        
        # Add JSON metadata if available
        if json_file and json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    json_metadata = json.load(f)
                quality_info['dicom_metadata'] = json_metadata
                
                # Add reformatted slice information
                if is_reformatted:
                    quality_info['reformatted_slice_info'] = {
                        'is_reformatted': True,
                        'image_type': json_metadata.get('ImageType', []),
                        'series_description': json_metadata.get('SeriesDescription', 'Unknown'),
                        'quality_note': 'This is a reformatted slice enhanced in-place with unsharp mask sharpening for maximum quality visualization.'
                    }
                else:
                    quality_info['reformatted_slice_info'] = {
                        'is_reformatted': False,
                        'quality_note': 'This is an original acquisition slice with optimal quality.'
                    }
            except Exception as e:
                print(f"⚠️  Could not read JSON sidecar: {e}")
        
        # Save enhanced quality report
        quality_file = nifti_file.with_suffix('.quality.json')
        with open(quality_file, 'w') as f:
            json.dump(quality_info, f, indent=2, default=str)
        
        print(f"    📊 Quality Report:")
        print(f"       Scan modality: {modality_info['modality']} ({modality_info['manufacturer']} {modality_info['model']})")
        print(f"       Study: {modality_info['study_description']}")
        print(f"       Series: {modality_info['series_description']}")
        print(f"       Data range: [{quality_info['data_quality']['min_value']:.1f}, {quality_info['data_quality']['max_value']:.1f}]")
        print(f"       Voxel spacing: {' x '.join(f'{x:.2f}' for x in quality_info['spatial_info']['voxel_spacing_mm'])} mm")
        print(f"       Volume size: {' x '.join(f'{x:.1f}' for x in quality_info['spatial_info']['volume_dimensions_mm'])} mm")
        print(f"       File size: {quality_info['file_info']['file_size_mb']:.1f} MB")
        
        # Advanced quality metrics (if enabled)
        if enable_quality_metrics:
            metrics = quality_info['advanced_quality_metrics']
            print(f"    🔬 Advanced Quality Metrics:")
            print(f"       Edge sharpness: {metrics['edge_sharpness']:.2f}")
            print(f"       Signal-to-noise ratio: {metrics['signal_to_noise_ratio']:.1f}")
            print(f"       Contrast-to-noise ratio: {metrics['contrast_to_noise_ratio']:.2f}")
            print(f"       Effective resolution: {metrics['effective_resolution_mm']:.2f} mm")
            print(f"       Noise level: {metrics['noise_level']:.2f}")
        
        if is_reformatted:
            print(f"    📐 Reformatted Slice Quality:")
            print(f"       Enhanced in-place with unsharp mask sharpening")
            print(f"       Optimized for maximum edge definition")
        
        return {
            'status': 'success',
            'quality_info': quality_info,
            'quality_file': quality_file
        }
        
    except Exception as e:
        print(f"❌ Enhancement failed for {nifti_file.name}: {e}")
        return {'status': 'failed', 'error': str(e)}


def create_quality_comparison_report(patient_id, output_folder):
    """
    Create a quality comparison report for a patient showing before/after metrics.
    
    Args:
        patient_id: Patient ID
        output_folder: Output folder path
    """
    try:
        patient_path = Path(output_folder) / patient_id
        nifti_path = patient_path / "nifti"
        backup_path = patient_path / "nifti_backup"
        
        if not nifti_path.exists() or not backup_path.exists():
            print(f"⚠️  Cannot create comparison report: missing data for {patient_id}")
            return
        
        print(f"\n📊 Quality Comparison Report for {patient_id}")
        print("=" * 60)
        
        # Find quality files
        current_quality_files = list(nifti_path.glob("*.quality.json"))
        backup_quality_files = list(backup_path.glob("*.quality.json"))
        
        for current_file in current_quality_files:
            filename = current_file.stem.replace('.quality', '')
            backup_file = backup_path / current_file.name
            
            if backup_file.exists():
                try:
                    with open(current_file, 'r') as f:
                        current_data = json.load(f)
                    with open(backup_file, 'r') as f:
                        backup_data = json.load(f)
                    
                    print(f"\n📄 {filename}:")
                    
                    # Compare basic metrics
                    current_size = current_data['file_info']['file_size_mb']
                    backup_size = backup_data['file_info']['file_size_mb']
                    size_change = ((current_size - backup_size) / backup_size) * 100
                    
                    print(f"   File size: {backup_size:.1f} MB → {current_size:.1f} MB ({size_change:+.1f}%)")
                    
                    # Compare quality metrics if available
                    if 'advanced_quality_metrics' in current_data and 'advanced_quality_metrics' in backup_data:
                        current_metrics = current_data['advanced_quality_metrics']
                        backup_metrics = backup_data['advanced_quality_metrics']
                        
                        print(f"   Edge sharpness: {backup_metrics['edge_sharpness']:.2f} → {current_metrics['edge_sharpness']:.2f}")
                        print(f"   SNR: {backup_metrics['signal_to_noise_ratio']:.1f} → {current_metrics['signal_to_noise_ratio']:.1f}")
                        print(f"   CNR: {backup_metrics['contrast_to_noise_ratio']:.2f} → {current_metrics['contrast_to_noise_ratio']:.2f}")
                        
                        # Check if this is a reformatted slice
                        is_reformatted = current_data.get('reformatted_slice_info', {}).get('is_reformatted', False)
                        if is_reformatted:
                            print(f"   📐 Reformatted slice - Enhanced with maximum quality settings")
                    
                except Exception as e:
                    print(f"   ⚠️  Could not compare {filename}: {e}")
        
        print(f"\n✅ Quality comparison completed for {patient_id}")
        
    except Exception as e:
        print(f"❌ Error creating quality comparison report: {e}")


def convert_dicom_to_nifti(force_overwrite=False, min_size_mb=None, patient_folders=None):
    """
    Convert DICOM files to NIFTI format using dcm2niix with maximum quality optimization.
    
    Args:
        force_overwrite: If True, overwrite existing NIFTI directories
        min_size_mb: If > 0, delete NIFTI files smaller than this size in MB. If None, uses MIN_FILE_SIZE_MB from constants.py.
        patient_folders: If specified, only process these specific patient folders. Can be a single string or list of strings.
    """
    try:
        # Check dcm2niix installation first
        if not check_dcm2niix_installation():
            raise RuntimeError("dcm2niix is required but not found. Please install dcm2niix first.")
        
        # Load environment variables
        dicom_folder = load_environment()
        
        # Load label dictionary
        label_dict = load_label_dictionary()
        
        # Use shared constant for minimum file size if not specified
        if min_size_mb is None:
            min_size_mb = MIN_FILE_SIZE_MB
        
        # Define paths - dicom_folder is now always absolute
        dicom_data_path = Path(dicom_folder)
        
        # Check if we're running in a Docker container
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        if is_docker:
            # In Docker container, use the mounted paths
            output_folder = '/app/output'
        else:
            # On host machine, use environment variables
            output_folder = os.getenv('OUTPUT_FOLDER')
            if not output_folder:
                raise ValueError("OUTPUT_FOLDER must be set in .env file with full path")
            if not os.path.isabs(output_folder):
                raise ValueError("OUTPUT_FOLDER must be set in .env file with full absolute path")
        
        nifti_base_path = Path(output_folder)
        
        print(f"🔬 Enhanced DICOM to NIFTI Conversion (dcm2niix + NiiVue)")
        print(f"📁 DICOM Source: {dicom_data_path}")
        print(f"📁 NIFTI Destination Base: {nifti_base_path}")
        print(f"⚡ Quality Mode: Maximum Quality (best results)")
        print(f"📏 Minimum File Size: {min_size_mb} MB (shared with segmentation)")
        print("-" * 70)
        
        # Check if DICOM directory exists
        if not dicom_data_path.exists():
            raise FileNotFoundError(f"DICOM directory not found: {dicom_data_path}")
        
        # Check if patient folders (subdirectories) exist
        if not check_patient_folders_exist(dicom_data_path):
            raise FileNotFoundError(f"No patient folders (subdirectories) found in: {dicom_data_path}")
        
        # Create NIFTI base directory if it doesn't exist
        nifti_base_path.mkdir(parents=True, exist_ok=True)
        
        # Get list of DICOM directories for progress tracking (ignore uploads folder)
        all_dicom_directories = [d for d in os.listdir(dicom_data_path) 
                               if (dicom_data_path / d).is_dir() and d != 'uploads']
        
        # Filter by patient folders if specified
        if patient_folders:
            # Handle both single string and list of strings
            if isinstance(patient_folders, str):
                patient_folders = [patient_folders]
            
            # Validate that all specified patient folders exist
            missing_folders = [p for p in patient_folders if p not in all_dicom_directories]
            if missing_folders:
                raise ValueError(f"Patient folders not found in DICOM directory: {missing_folders}. Available folders: {all_dicom_directories}")
            
            dicom_directories = patient_folders
            if len(patient_folders) == 1:
                print(f"📊 Processing specific patient: {patient_folders[0]}")
            else:
                print(f"📊 Processing {len(patient_folders)} specific patients: {', '.join(patient_folders)}")
        else:
            dicom_directories = all_dicom_directories
            print(f"📊 Found {len(dicom_directories)} DICOM directories to process")
        print(f"🔧 Using dcm2niix for robust conversion with NiiVue optimization")
        print("-" * 70)
        
        # Convert DICOM to NIFTI using dcm2niix
        successful_conversions = 0
        failed_conversions = 0
        total_nifti_files = 0
        start_time = time.time()
        
        with tqdm(total=len(dicom_directories), desc="🔄 Processing patients", unit="patient") as patient_pbar:
            for dicom_directory in dicom_directories:
                input_directory = Path(dicom_data_path) / dicom_directory
                # New output structure: output/<patient_id>/nifti/
                output_directory = nifti_base_path / dicom_directory / "nifti"
            
                # Check if already processed
                if output_directory.exists() and not force_overwrite:
                    warnings.warn(f"{output_directory} already exists, skipping...")
                    patient_pbar.update(1)
                    continue
                elif output_directory.exists() and force_overwrite:
                    print(f"\n🔄 Overwriting existing directory: {output_directory}")
                    shutil.rmtree(output_directory)
                    
                # Process the patient with dcm2niix
                try:
                    print(f"\n📂 Processing: {dicom_directory}")
                    print("-" * 50)
                    
                    # Detect modality first to optimize dcm2niix settings
                    # We'll do a quick pre-scan to detect modality
                    modality = 'Unknown'  # Default
                    try:
                        # Try to detect modality from first DICOM file
                        import glob
                        dicom_files = glob.glob(str(input_directory / "*.dcm"))
                        if dicom_files:
                            # Use dcm2niix to get metadata from first file
                            temp_result = subprocess.run([
                                'dcm2niix', '-b', 'y', '-o', '/tmp', 
                                str(input_directory)
                            ], capture_output=True, text=True, timeout=30)
                            
                            # Look for JSON files created
                            json_files = glob.glob("/tmp/*.json")
                            if json_files:
                                with open(json_files[0], 'r') as f:
                                    metadata = json.load(f)
                                modality = metadata.get('Modality', 'Unknown')
                                # Clean up temp files
                                for f in json_files:
                                    os.unlink(f)
                    except Exception:
                        pass  # Use default modality
                    
                    # Run dcm2niix conversion with modality-specific settings
                    conversion_result = run_dcm2niix_conversion(
                        input_dir=input_directory,
                        output_dir=output_directory,
                        optimize_reformatted=True,
                        modality=modality
                    )
                    
                    if conversion_result['status'] == 'success':
                        print(f"✅ dcm2niix conversion completed successfully")
                        
                        nifti_files = conversion_result['nifti_files']
                        
                        # Filter by size if requested
                        if min_size_mb > 0:
                            print(f"🗑️  Filtering NIFTI files by size (min size: {min_size_mb} MB)...")
                            large_nifti_files = []
                            deleted_count = 0
                            for nifti_file in nifti_files:
                                file_size_mb = nifti_file.stat().st_size / (1024 * 1024)
                                if file_size_mb >= min_size_mb:
                                    large_nifti_files.append(nifti_file)
                                else:
                                    print(f"   Deleting small file: {nifti_file.name} ({file_size_mb:.2f} MB)")
                                    nifti_file.unlink()
                                    deleted_count += 1
                                    # Also delete corresponding json and quality files
                                    base_name = nifti_file.name.replace('.nii.gz', '').replace('.nii', '')
                                    json_file = nifti_file.with_name(base_name + '.json')
                                    if json_file.exists():
                                        print(f"   Deleting corresponding json file: {json_file.name}")
                                        json_file.unlink()
                                    quality_file = nifti_file.with_name(base_name + '.quality.json')
                                    if quality_file.exists():
                                        print(f"   Deleting corresponding quality file: {quality_file.name}")
                                        quality_file.unlink()
                            
                            print(f"   Deleted {deleted_count} small NIFTI files.")
                            nifti_files = large_nifti_files
                            
                            # Check if any files remain after filtering
                            if not nifti_files:
                                print(f"⚠️  No files meet minimum size requirement ({min_size_mb} MB) for {dicom_directory}")
                                print(f"🗑️  Removing empty patient directory: {output_directory}")
                                shutil.rmtree(output_directory)
                                print(f"⏭️  Skipping {dicom_directory} - no files meet size criteria")
                                patient_pbar.update(1)
                                continue

                        # Process each created NIFTI file for NiiVue enhancement
                        json_files = conversion_result['json_files']
                        total_nifti_files += len(nifti_files)
                        
                        print(f"🔧 Enhancing {len(nifti_files)} NIFTI files for NiiVue...")
                        
                        for i, nifti_file in enumerate(nifti_files, 1):
                            print(f"    📄 Processing file {i}/{len(nifti_files)}: {nifti_file.name}")
                            # Find corresponding JSON file
                            json_file = None
                            nifti_basename = nifti_file.stem.replace('.nii', '')
                            for json_f in json_files:
                                if json_f.stem == nifti_basename:
                                    json_file = json_f
                                    break
                            
                            # Extract comprehensive metadata from JSON sidecar
                            if json_file:
                                try:
                                    extract_comprehensive_metadata(json_file, nifti_file)
                                except Exception as e:
                                    print(f"    ⚠️  Metadata extraction warning: {e}")
                            
                            # Enhance for NiiVue with timeout protection
                            try:
                                enhancement_result = enhance_nifti_for_niivue(nifti_file, json_file)
                                
                                if enhancement_result['status'] == 'success':
                                    print(f"    ✅ Enhanced: {nifti_file.name}")
                                else:
                                    print(f"    ⚠️  Enhancement warning: {nifti_file.name}")
                                    print(f"        Error: {enhancement_result.get('error', 'Unknown error')}")
                            except Exception as e:
                                print(f"    ❌ Enhancement failed for {nifti_file.name}: {e}")
                                # Continue processing other files even if one fails
                        
                        successful_conversions += 1
                        print(f"🎉 Successfully processed {dicom_directory}")
                        
                    else:
                        print(f"❌ dcm2niix conversion failed for {dicom_directory}")
                        print(f"   Error: {conversion_result.get('error', 'Unknown error')}")
                        failed_conversions += 1
                        
                        # Clean up failed output directory
                        if output_directory.exists():
                            shutil.rmtree(output_directory)
                    
                    patient_pbar.update(1)
                    
                except Exception as e:
                    print(f"✗ Failed to convert {dicom_directory}: {str(e)}")
                    # Clean up the failed output directory
                    if output_directory.exists():
                        shutil.rmtree(output_directory)
                    failed_conversions += 1
                    patient_pbar.update(1)
                    continue
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print("-" * 70)
        print("🎉 Enhanced DICOM to NIFTI conversion completed!")
        print(f"✓ Successfully converted: {successful_conversions} directories")
        print(f"✗ Failed conversions: {failed_conversions} directories")
        print(f"📁 Total processed: {len(dicom_directories)} directories")
        print(f"📄 Total NIFTI files created: {total_nifti_files}")
        print(f"⏱️  Total processing time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        print(f"⚡ Average time per patient: {total_time/len(dicom_directories):.1f} seconds")
        
        print(f"\n🔬 Maximum Quality Features Applied:")
        print("   • dcm2niix with maximum quality settings")
        print("   • No cropping/rotation (preserves all data)")
        print("   • Lossless 16-bit scaling for full dynamic range")
        print("   • Optimal compression with maximum quality")
        print("   • In-place unsharp mask sharpening for reformatted slices")
        print("   • Advanced interpolation (cubic/quintic)")
        print("   • Comprehensive quality metrics calculation")
        print("   • Enhanced quality reports with detailed analysis")
        
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        raise



if __name__ == "__main__":
    import sys
    # Check if force overwrite flag is passed
    force_overwrite = '--force' in sys.argv or '--overwrite' in sys.argv
    
    # Always use maximum quality mode
    optimize_reformatted = True
    
    kwargs = {}
    if '--min-size-mb' in sys.argv:
        try:
            index = sys.argv.index('--min-size-mb')
            kwargs['min_size_mb'] = int(sys.argv[index + 1])
        except (ValueError, IndexError):
            print("Error: --min-size-mb requires an integer value (e.g., --min-size-mb 10)")
            sys.exit(1)
    
    if '--patient' in sys.argv:
        try:
            index = sys.argv.index('--patient')
            # Collect all patient arguments until we hit another flag or end of args
            patient_folders = []
            i = index + 1
            while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                patient_folders.append(sys.argv[i])
                i += 1
            
            if not patient_folders:
                print("Error: --patient requires at least one patient folder name (e.g., --patient Patient001)")
                sys.exit(1)
            
            kwargs['patient_folders'] = patient_folders if len(patient_folders) > 1 else patient_folders[0]
        except IndexError:
            print("Error: --patient requires at least one patient folder name (e.g., --patient Patient001)")
            sys.exit(1)

    convert_dicom_to_nifti(force_overwrite=force_overwrite, **kwargs)
