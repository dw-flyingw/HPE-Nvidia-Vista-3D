"""
Voxel Manager for Vista3D Application
Handles voxel selection, overlay management, and related logic.
"""

from typing import List, Dict, Optional, Any, Set, Tuple
import os
import json
import requests
from bs4 import BeautifulSoup
from .config_manager import ConfigManager
from .data_manager import DataManager
from .constants import OUTPUT_FOLDER_ABS, OUTPUT_DIR, VOXELS_DIR


class VoxelManager:
    """
    Manages voxel selection and overlay configuration.
    Provides a clean interface for handling different voxel display modes.
    Folder structure: output/patient/voxels/scan_name/
    """

    def __init__(self, config_manager: ConfigManager, data_manager: DataManager):
        self.config = config_manager
        self.data = data_manager

    def has_voxels_for_patient(self, patient_id: str) -> bool:
        """
        Check if there are any voxels available for the given patient.
        Returns True if voxels exist, False otherwise.
        Folder structure: output/patient/voxels/scan_name/
        """
        if not patient_id:
            return False
        
        # First try to check via image server
        try:
            voxels_folder_url = f"{self.data.image_server_url}/output/{patient_id}/voxels/"
            
            resp = requests.get(voxels_folder_url, timeout=5)
            if resp.status_code == 200:
                # Parse directory listing to see if there are any scan subdirectories
                soup = BeautifulSoup(resp.text, 'html.parser')
                scan_subdirs = []
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href and not href.startswith('..') and href.endswith('/'):
                        scan_subdirs.append(href)
                
                # Check if any of the scan subdirectories contain .nii.gz files
                for scan_subdir in scan_subdirs:
                    scan_url = f"{self.data.image_server_url}{scan_subdir}"
                    scan_resp = requests.get(scan_url, timeout=5)
                    if scan_resp.status_code == 200:
                        scan_soup = BeautifulSoup(scan_resp.text, 'html.parser')
                        for link in scan_soup.find_all('a'):
                            href = link.get('href')
                            if href and href.endswith('.nii.gz') and not href.startswith('..'):
                                return True
        except Exception:
            pass  # Fall through to local filesystem check
        
        # Fallback: Check local filesystem
        try:
            voxels_folder_path = os.path.join(OUTPUT_FOLDER_ABS, patient_id, 'voxels')
            
            if not os.path.exists(voxels_folder_path):
                return False
            
            # Check if there are any scan subdirectories containing .nii.gz files
            for scan_item in os.listdir(voxels_folder_path):
                scan_path = os.path.join(voxels_folder_path, scan_item)
                if os.path.isdir(scan_path):
                    # This is a scan directory, check for .nii.gz files
                    for file in os.listdir(scan_path):
                        if file.endswith('.nii.gz'):
                            return True
            
            return False
            
        except Exception:
            return False

    def get_available_voxels(
        self,
        patient_id: str,
        filename: str
    ) -> Tuple[Set[int], Dict[int, str], List[str]]:
        """
        Get available voxel information for the given patient and file.
        Returns (available_ids, id_to_path_map, available_voxel_names).
        """
        # Return empty results if filename is None
        if filename is None:
            return set(), {}, []
            
        # Detect scan modality to filter appropriate structures
        scan_modality = self._detect_scan_modality(patient_id, filename)
            
        # Query server for actually available voxel files
        filename_to_id = self.config.create_filename_to_id_mapping()
            
        available_ids, id_to_path_map = self.data.fetch_available_voxel_labels(
            patient_id, filename, filename_to_id
        )

        # Get names for available labels, filtered by modality
        available_voxel_names = []
        for name, label_id in self.config.label_dict.items():
            if isinstance(label_id, int) and label_id in available_ids:
                # Filter out inappropriate structures for brain scans
                if scan_modality == 'brain' and not self._is_brain_relevant_structure(label_id, name):
                    continue
                available_voxel_names.append(name)

        return available_ids, id_to_path_map, sorted(available_voxel_names)

    def create_overlays(
        self,
        patient_id: str,
        filename: str,
        selected_voxels: Optional[List[str]] = None,
        external_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Create overlay configuration based on selected voxels.
        Folder structure: output/patient/voxels/scan_name/
        """
        overlays = []
        
        # Return empty list if filename is None or no voxels selected
        if filename is None or not selected_voxels:
            return overlays
        
        # Use external URL for browser access if provided, otherwise use internal URL
        base_url = external_url if external_url else self.data.image_server_url

        # Determine the folder structure
        ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '')

        # Detect scan modality to filter appropriate anatomical structures
        scan_modality = self._detect_scan_modality(patient_id, filename)
        
        # Get available voxels to check if all are selected
        available_ids, id_to_path_map, available_voxel_names = self.get_available_voxels(
            patient_id, filename
        )

        # Determine if voxel files share a common subdirectory (e.g., "original/")
        path_prefixes = {
            path.rsplit('/', 1)[0]
            for path in id_to_path_map.values()
            if '/' in path
        }
        common_prefix = path_prefixes.pop() if len(path_prefixes) == 1 else ''
        
        # If all available voxels are selected, use all.nii.gz for better performance
        if available_voxel_names and set(selected_voxels) == set(available_voxel_names):
            print(f"DEBUG: All {len(available_voxel_names)} voxels selected - loading all.nii.gz")
            all_relative_path = f"{common_prefix}/all.nii.gz" if common_prefix else "all.nii.gz"
            overlays.append({
                'label_id': 'all',
                'label_name': 'All Segmentation',
                'url': f"{base_url}/{OUTPUT_DIR}/{patient_id}/{VOXELS_DIR}/{ct_scan_folder_name}/{all_relative_path}",
                'use_custom_colormap': True  # Flag to use customSegmentationColormap
            })
            return overlays
        
        # Otherwise, create overlays for individual selected voxels
        print(f"DEBUG: Creating individual overlays for {len(selected_voxels)} voxels")
        for voxel_name in selected_voxels:
            if voxel_name in self.config.label_dict:
                label_id = self.config.label_dict[voxel_name]
                
                # Filter out inappropriate structures for brain scans
                if scan_modality == 'brain' and not self._is_brain_relevant_structure(label_id, voxel_name):
                    continue

                # Convert voxel name to filename format
                voxel_filename = voxel_name.lower().replace(' ', '_').replace('-', '_') + '.nii.gz'

                # Get color for this label
                label_color = self.config.get_label_color(label_id)

                relative_path = id_to_path_map.get(label_id)
                if not relative_path:
                    relative_path = f"{common_prefix}/{voxel_filename}" if common_prefix else voxel_filename

                overlays.append({
                    'label_id': label_id,
                    'label_name': voxel_name,
                    'url': f"{base_url}/{OUTPUT_DIR}/{patient_id}/{VOXELS_DIR}/{ct_scan_folder_name}/{relative_path}",
                    'color': label_color
                })
        
        print(f"DEBUG: Created {len(overlays)} overlays from {len(selected_voxels)} selected voxels")
        return overlays

    def create_custom_colormap_js(self) -> str:
        """Generate JavaScript for custom segmentation colormap."""
        try:
            label_colors_list = self.config.label_colors
            if not label_colors_list:
                print("ERROR: No label colors found in config!")
                return ""

            print(f"DEBUG (VoxelManager): Creating colormap from {len(label_colors_list)} labels")
            
            r_values, g_values, b_values, a_values, labels = [0]*256, [0]*256, [0]*256, [0]*256, [""]*256
            r_values[0], g_values[0], b_values[0], a_values[0], labels[0] = 0, 0, 0, 0, "Background"

            max_id = 0
            for item in label_colors_list:
                idx = item.get('id', 0)
                label_name = item.get('name', '')
                color = item.get('color', [0, 0, 0])

                if 0 <= idx < 256:
                    r_values[idx] = color[0]
                    g_values[idx] = color[1]
                    b_values[idx] = color[2]
                    a_values[idx] = 255
                    labels[idx] = label_name

                if idx > max_id:
                    max_id = idx
            
            # Debug: Print first few colors
            print(f"DEBUG (VoxelManager): Sample colors:")
            print(f"  ID 1 (liver): RGB({r_values[1]}, {g_values[1]}, {b_values[1]})")
            print(f"  ID 3 (spleen): RGB({r_values[3]}, {g_values[3]}, {b_values[3]})")
            print(f"  ID 5 (right kidney): RGB({r_values[5]}, {g_values[5]}, {b_values[5]})")
            print(f"  ID 6 (aorta): RGB({r_values[6]}, {g_values[6]}, {b_values[6]})")
            print(f"  Max ID: {max_id}")

            # Trim arrays to max_id + 1 for efficiency
            r_values = r_values[:max_id+1]
            g_values = g_values[:max_id+1]
            b_values = b_values[:max_id+1]
            a_values = a_values[:max_id+1]
            labels = labels[:max_id+1]
            
            print(f"DEBUG (VoxelManager): Trimmed colormap to {len(r_values)} entries")

            # Format labels for JavaScript
            js_labels = []
            for label in labels:
                escaped_label = label.replace('"', '\\"')
                js_labels.append(f'"{escaped_label}"')
            labels_string = ",".join(js_labels)

            return f"""
            const customSegmentationColormap = {{
                R: [{",".join(map(str, r_values))}],
                G: [{",".join(map(str, g_values))}],
                B: [{",".join(map(str, b_values))}],
                A: [{",".join(map(str, a_values))}],
                labels: [{labels_string}],
                maxLabelId: {max_id}
            }};
            console.log('Vista3D colormap loaded from vista3d_label_colors.json:', customSegmentationColormap);
            console.log('  Colormap has', customSegmentationColormap.R.length, 'entries, max label ID:', customSegmentationColormap.maxLabelId);
            """

        except Exception as e:
            print(f"Error creating custom colormap: {e}")
            return ""

    def get_voxel_legend_html(self) -> str:
        """Generate HTML for the voxel legend display."""
        try:
            legend_items = []
            for label_info in self.config.label_colors:
                label_name = label_info.get("name", "")
                label_id = label_info.get("id", 0)
                color_rgb = label_info.get("color", [0, 0, 0])
                color_hex = f"#{color_rgb[0]:02x}{color_rgb[1]:02x}{color_rgb[2]:02x}"

                legend_items.append(f'''
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <div style="width: 20px; height: 20px; background-color: {color_hex}; border: 1px solid #ccc; margin-right: 10px;"></div>
                    <span>{label_name} (ID: {label_id})</span>
                </div>''')

            return "".join(legend_items)

        except Exception as e:
            return f'<div style="color: red;">Error loading segment colors: {e}</div>'

    def _detect_scan_modality(self, patient_id: str, filename: str) -> str:
        """
        Detect if this is a brain scan based on filename patterns and metadata.
        Returns 'brain' for brain scans, 'body' for other scans.
        """
        if not filename:
            return 'body'
            
        # Check filename for brain-related patterns
        filename_lower = filename.lower()
        brain_keywords = ['brain', 'mri', 't1', 't2', 'flair', 'dwi', 'adc', 'swi', 'gre', 'irspgr']
        
        for keyword in brain_keywords:
            if keyword in filename_lower:
                return 'brain'
        
        # Check metadata if available
        try:
            import os
            import json
            from .constants import OUTPUT_FOLDER_ABS
            
            base_filename = filename.replace('.nii.gz', '').replace('.nii', '')
            metadata_file = os.path.join(OUTPUT_FOLDER_ABS, patient_id, "nifti", f"{base_filename}.json")
            
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check modality
                modality = metadata.get('Modality', '').upper()
                if modality == 'MR':
                    return 'brain'
                    
                # Check study description
                study_desc = metadata.get('StudyDescription', '').lower()
                if any(keyword in study_desc for keyword in ['brain', 'head', 'skull', 'cranial']):
                    return 'brain'
                    
        except Exception:
            pass  # Fall back to filename-based detection
        
        return 'body'

    def _is_brain_relevant_structure(self, label_id: int, structure_name: str) -> bool:
        """
        Check if a structure is relevant for brain imaging.
        Returns True for brain-relevant structures, False for body structures.
        """
        # Brain-relevant structures (based on label IDs and names)
        brain_relevant_ids = {
            22,  # brain
            120, # skull
            121, # spinal cord
            57,  # trachea (upper part)
            115, # heart (for brain-heart connection studies)
            125, # superior vena cava (for brain blood flow)
            126, # thyroid gland (for brain-thyroid studies)
        }
        
        brain_relevant_names = [
            'brain', 'skull', 'spinal cord', 'trachea', 'heart', 
            'superior vena cava', 'thyroid gland', 'airway'
        ]
        
        # Check by label ID
        if label_id in brain_relevant_ids:
            return True
            
        # Check by structure name
        structure_lower = structure_name.lower()
        if any(name in structure_lower for name in brain_relevant_names):
            return True
            
        return False

    def _get_brain_relevant_structures(self) -> List[str]:
        """
        Get list of brain-relevant anatomical structures.
        """
        brain_structures = []
        
        for label_info in self.config.label_colors:
            label_id = label_info.get('id')
            label_name = label_info.get('name', '')
            
            if self._is_brain_relevant_structure(label_id, label_name):
                brain_structures.append(label_name)
                
        return brain_structures

    def _create_brain_filtered_overlay(self, patient_id: str, filename: str, base_url: str) -> Optional[Dict[str, Any]]:
        """
        Create a filtered overlay that only shows brain-relevant structures.
        For brain scans where Vista3D has misclassified structures, create a proper brain segmentation.
        """
        try:
            import os
            import nibabel as nib
            import numpy as np
            from .constants import OUTPUT_FOLDER_ABS, OUTPUT_DIR, VOXELS_DIR
            
            # Path to segmentation
            ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '')
            original_seg_path = os.path.join(
                OUTPUT_FOLDER_ABS, patient_id, VOXELS_DIR, ct_scan_folder_name, 
                'all.nii.gz'
            )
            
            if not os.path.exists(original_seg_path):
                return None
                
            # Load original segmentation
            original_img = nib.load(original_seg_path)
            data = original_img.get_fdata()
            
            # For brain scans, Vista3D often misclassifies structures
            # Create a proper brain segmentation by identifying the largest connected component
            # and treating it as brain tissue
            # Ensure we use integer data type for proper label handling
            filtered_data = np.zeros_like(data, dtype=np.int16)
            
            # Check if we have proper brain segmentation (label 22)
            brain_mask = (data == 22)
            brain_voxels = np.count_nonzero(brain_mask)
            
            if brain_voxels > 1000:  # If brain segmentation is reasonable
                # Use the existing brain segmentation
                filtered_data[brain_mask] = 22
            else:
                # Vista3D has misclassified - create brain segmentation
                # For brain MRI scans, look for brain tissue in the upper portion of the image
                from scipy import ndimage
                
                # Get all non-zero labels
                non_zero_mask = (data > 0)
                if np.any(non_zero_mask):
                    # For brain scans, focus on the upper 2/3 of the image where brain tissue should be
                    height = data.shape[2]  # Assuming Z is the slice dimension
                    upper_slice_start = height // 3  # Start from upper 2/3
                    
                    # Create a mask for the upper portion
                    upper_mask = np.zeros_like(non_zero_mask, dtype=bool)
                    upper_mask[:, :, upper_slice_start:] = True
                    
                    # Only consider voxels in the upper portion
                    upper_non_zero_mask = non_zero_mask & upper_mask
                    
                    if np.any(upper_non_zero_mask):
                        # Label connected components in upper portion
                        labeled_array, num_features = ndimage.label(upper_non_zero_mask)
                        
                        if num_features > 0:
                            # Find the largest component in upper portion
                            component_sizes = [np.count_nonzero(labeled_array == i) for i in range(1, num_features + 1)]
                            largest_component = np.argmax(component_sizes) + 1
                            
                            # Use the largest component in upper portion as brain tissue
                            brain_mask = (labeled_array == largest_component)
                            filtered_data[brain_mask] = 22  # Label as brain
                            
                            print(f"Created brain segmentation from largest upper component: {np.count_nonzero(brain_mask)} voxels")
                    else:
                        # Fallback: use largest component from entire image
                        labeled_array, num_features = ndimage.label(non_zero_mask)
                        
                        if num_features > 0:
                            component_sizes = [np.count_nonzero(labeled_array == i) for i in range(1, num_features + 1)]
                            largest_component = np.argmax(component_sizes) + 1
                            
                            brain_mask = (labeled_array == largest_component)
                            filtered_data[brain_mask] = 22  # Label as brain
                            
                            print(f"Created brain segmentation from largest component (fallback): {np.count_nonzero(brain_mask)} voxels")
            
            # Add skull if available
            skull_mask = (data == 120)
            if np.any(skull_mask):
                filtered_data[skull_mask] = 120
                print(f"Added skull segmentation: {np.count_nonzero(skull_mask)} voxels")
            else:
                # Try to find bone structures (label 21) as potential skull
                bone_mask = (data == 21)
                if np.any(bone_mask):
                    # For brain scans, bone in upper portion might be skull
                    height = data.shape[2]
                    upper_slice_start = height // 3
                    upper_bone_mask = bone_mask.copy()
                    upper_bone_mask[:, :, :upper_slice_start] = False  # Remove lower portion
                    
                    if np.any(upper_bone_mask):
                        filtered_data[upper_bone_mask] = 120  # Label as skull
                        print(f"Added bone as skull segmentation: {np.count_nonzero(upper_bone_mask)} voxels")
                else:
                    # Try to create skull from brain boundary
                    if np.any(brain_mask):
                        from scipy import ndimage
                        # Dilate brain mask to create skull-like boundary
                        dilated_brain = ndimage.binary_dilation(brain_mask, structure=np.ones((3,3,3)))
                        skull_candidate = dilated_brain & ~brain_mask
                        
                        if np.any(skull_candidate):
                            filtered_data[skull_candidate] = 120  # Label as skull
                            print(f"Created skull from brain boundary: {np.count_nonzero(skull_candidate)} voxels")
            
            # Add other brain-relevant structures if they exist and are reasonable
            brain_structures = self._get_brain_relevant_structures()
            for structure_name in brain_structures:
                if structure_name in self.config.label_dict:
                    label_id = self.config.label_dict[structure_name]
                    structure_mask = (data == label_id)
                    structure_voxels = np.count_nonzero(structure_mask)
                    
                    # Only include if it has a reasonable number of voxels
                    if structure_voxels > 10:  # Minimum threshold
                        filtered_data[structure_mask] = label_id
                        print(f"Added {structure_name}: {structure_voxels} voxels")
            
            # Create filtered image with proper integer data type
            # Ensure the data is properly converted to int16
            filtered_data_int = filtered_data.astype(np.int16)
            filtered_img = nib.Nifti1Image(filtered_data_int, original_img.affine, original_img.header)
            
            # Save filtered segmentation
            filtered_path = original_seg_path.replace('all.nii.gz', 'brain_filtered.nii.gz')
            nib.save(filtered_img, filtered_path)
            
            total_voxels = np.count_nonzero(filtered_data)
            print(f"Created brain-filtered segmentation with {total_voxels} total voxels")
            
            return {
                'label_id': 'brain_filtered',
                'label_name': 'Brain Structures Only',
                'url': f"{base_url}/{OUTPUT_DIR}/{patient_id}/{VOXELS_DIR}/{ct_scan_folder_name}/brain_filtered.nii.gz",
                'is_all_segmentation': True
            }
            
        except Exception as e:
            print(f"Error creating brain filtered overlay: {e}")
            return None