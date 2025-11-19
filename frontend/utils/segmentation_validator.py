"""
Segmentation Validation and Cleanup Module for Vista-3D
Provides modular validation checks and cleanup functions for segmentation outputs.
"""

import numpy as np
import nibabel as nib
from typing import Dict, List, Optional, Tuple, Any
from scipy import ndimage


class SegmentationValidator:
    """
    Validates Vista-3D segmentation outputs for quality and correctness.
    All validation methods are modular and can be used independently.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validator with configuration.
        
        Args:
            config: Dictionary with validation thresholds and settings
        """
        self.config = config
        self.min_voxels_per_label = config.get('min_voxels_per_label', 10)
        self.min_voxels_per_component = config.get('min_voxels_per_component', 10)
        self.max_segmentation_ratio = config.get('max_segmentation_ratio', 0.95)
        self.min_segmentation_ratio = config.get('min_segmentation_ratio', 0.001)

    def validate_dimensions(
        self, 
        seg_img: nib.Nifti1Image, 
        input_img: Optional[nib.Nifti1Image]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that segmentation dimensions match input image.
        
        Args:
            seg_img: Segmentation NIfTI image
            input_img: Input NIfTI image (optional)
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        seg_shape = seg_img.shape
        seg_affine = seg_img.affine
        
        # Check segmentation has valid dimensions
        if len(seg_shape) < 3:
            errors.append(f"Segmentation has invalid dimensions: {seg_shape}")
            return False, errors
        
        # If input image provided, compare dimensions
        if input_img is not None:
            input_shape = input_img.shape
            input_affine = input_img.affine
            
            if seg_shape != input_shape:
                errors.append(
                    f"Dimension mismatch: segmentation {seg_shape} != input {input_shape}"
                )
            
            # Check affine matrices are similar (within tolerance)
            if not np.allclose(seg_affine, input_affine, atol=1e-3):
                errors.append("Affine matrix mismatch between segmentation and input")
        
        return len(errors) == 0, errors

    def validate_labels(
        self, 
        seg_data: np.ndarray, 
        label_dict: Dict[int, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate that all labels in segmentation are known/valid.
        
        Args:
            seg_data: Segmentation data array
            label_dict: Dictionary mapping label IDs to label info
            
        Returns:
            Tuple of (is_valid, list_of_warnings, list_of_errors)
        """
        warnings = []
        errors = []
        
        unique_labels = np.unique(seg_data)
        unique_labels = unique_labels[unique_labels != 0]  # Remove background
        
        unknown_labels = []
        for label_id in unique_labels:
            if int(label_id) not in label_dict:
                unknown_labels.append(int(label_id))
        
        if unknown_labels:
            warnings.append(
                f"Found {len(unknown_labels)} unknown label(s): {unknown_labels[:10]}"
                + (f" (showing first 10)" if len(unknown_labels) > 10 else "")
            )
        
        # Check for negative labels (shouldn't happen)
        negative_labels = unique_labels[unique_labels < 0]
        if len(negative_labels) > 0:
            errors.append(f"Found negative label IDs: {negative_labels}")
        
        return len(errors) == 0, warnings, errors

    def validate_voxel_counts(
        self, 
        seg_data: np.ndarray, 
        label_dict: Dict[int, Any],
        total_voxels: int
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate voxel counts per label and overall segmentation ratio.
        
        Args:
            seg_data: Segmentation data array
            label_dict: Dictionary mapping label IDs to label info
            total_voxels: Total number of voxels in the image
            
        Returns:
            Tuple of (is_valid, list_of_warnings, list_of_errors)
        """
        warnings = []
        errors = []
        
        unique_labels = np.unique(seg_data)
        unique_labels = unique_labels[unique_labels != 0]  # Remove background
        
        # Count voxels per label
        segmented_voxels = np.count_nonzero(seg_data)
        segmentation_ratio = segmented_voxels / total_voxels if total_voxels > 0 else 0
        
        # Check overall segmentation ratio
        if segmentation_ratio > self.max_segmentation_ratio:
            warnings.append(
                f"Segmentation covers {segmentation_ratio:.1%} of volume "
                f"(exceeds {self.max_segmentation_ratio:.1%} threshold) - possible over-segmentation"
            )
        elif segmentation_ratio < self.min_segmentation_ratio:
            warnings.append(
                f"Segmentation covers only {segmentation_ratio:.1%} of volume "
                f"(below {self.min_segmentation_ratio:.1%} threshold) - possible under-segmentation"
            )
        
        # Check voxel counts per label
        small_labels = []
        for label_id in unique_labels:
            label_mask = (seg_data == label_id)
            voxel_count = np.count_nonzero(label_mask)
            
            if voxel_count < self.min_voxels_per_label:
                label_name = label_dict.get(int(label_id), {}).get('name', f'Label {label_id}')
                small_labels.append(f"{label_name} (ID: {label_id}): {voxel_count} voxels")
        
        if small_labels:
            warnings.append(
                f"Found {len(small_labels)} label(s) with < {self.min_voxels_per_label} voxels: "
                + ", ".join(small_labels[:5])
                + (f" (showing first 5 of {len(small_labels)})" if len(small_labels) > 5 else "")
            )
        
        return len(errors) == 0, warnings, errors

    def validate_spatial_consistency(
        self, 
        seg_data: np.ndarray
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate spatial consistency by checking for isolated components.
        
        Args:
            seg_data: Segmentation data array
            
        Returns:
            Tuple of (is_valid, list_of_warnings, list_of_errors)
        """
        warnings = []
        errors = []
        
        unique_labels = np.unique(seg_data)
        unique_labels = unique_labels[unique_labels != 0]  # Remove background
        
        total_small_components = 0
        for label_id in unique_labels:
            label_mask = (seg_data == label_id)
            
            # Find connected components for this label
            labeled_array, num_features = ndimage.label(label_mask)
            
            if num_features > 1:
                # Check component sizes
                component_sizes = [
                    np.count_nonzero(labeled_array == i) 
                    for i in range(1, num_features + 1)
                ]
                small_components = [
                    size for size in component_sizes 
                    if size < self.min_voxels_per_component
                ]
                total_small_components += len(small_components)
        
        if total_small_components > 0:
            warnings.append(
                f"Found {total_small_components} small isolated component(s) "
                f"(< {self.min_voxels_per_component} voxels each) - possible noise"
            )
        
        return len(errors) == 0, warnings, errors

    def validate_statistics(
        self, 
        seg_data: np.ndarray, 
        input_data: Optional[np.ndarray]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Perform statistical validation of segmentation.
        
        Args:
            seg_data: Segmentation data array
            input_data: Input image data array (optional)
            
        Returns:
            Tuple of (is_valid, list_of_warnings, list_of_errors)
        """
        warnings = []
        errors = []
        
        # Check for uniform/empty regions
        unique_labels = np.unique(seg_data)
        if len(unique_labels) == 1 and unique_labels[0] == 0:
            errors.append("Segmentation is completely empty (only background)")
            return False, warnings, errors
        
        # Check label distribution
        label_counts = {}
        for label_id in unique_labels:
            if label_id != 0:
                count = np.count_nonzero(seg_data == label_id)
                label_counts[int(label_id)] = count
        
        # Warn if one label dominates (>90% of segmented voxels)
        if label_counts:
            total_segmented = sum(label_counts.values())
            max_label_count = max(label_counts.values())
            max_ratio = max_label_count / total_segmented if total_segmented > 0 else 0
            
            if max_ratio > 0.9:
                max_label_id = max(label_counts, key=label_counts.get)
                warnings.append(
                    f"Single label (ID: {max_label_id}) dominates segmentation "
                    f"({max_ratio:.1%} of segmented voxels)"
                )
        
        return len(errors) == 0, warnings, errors


class SegmentationCleaner:
    """
    Cleans up Vista-3D segmentation outputs by removing noise and artifacts.
    All cleanup methods are modular and can be used independently.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cleaner with configuration.
        
        Args:
            config: Dictionary with cleanup settings
        """
        self.config = config
        self.min_voxels_per_component = config.get('min_voxels_per_component', 10)

    def remove_small_components(
        self, 
        seg_data: np.ndarray, 
        min_voxels: Optional[int] = None
    ) -> Tuple[np.ndarray, int]:
        """
        Remove small connected components (noise) from segmentation.
        
        Args:
            seg_data: Segmentation data array
            min_voxels: Minimum voxels per component (uses config default if None)
            
        Returns:
            Tuple of (cleaned_data, num_components_removed)
        """
        if min_voxels is None:
            min_voxels = self.min_voxels_per_component
        
        cleaned_data = seg_data.copy()
        total_removed = 0
        
        unique_labels = np.unique(seg_data)
        unique_labels = unique_labels[unique_labels != 0]  # Remove background
        
        for label_id in unique_labels:
            label_mask = (cleaned_data == label_id)
            
            # Find connected components for this label
            labeled_array, num_features = ndimage.label(label_mask)
            
            if num_features > 0:
                # Get component sizes
                component_sizes = [
                    np.count_nonzero(labeled_array == i) 
                    for i in range(1, num_features + 1)
                ]
                
                # Remove small components
                for i, size in enumerate(component_sizes, start=1):
                    if size < min_voxels:
                        component_mask = (labeled_array == i)
                        cleaned_data[component_mask] = 0
                        total_removed += 1
        
        return cleaned_data, total_removed

    def clean_artifacts(
        self, 
        seg_data: np.ndarray
    ) -> Tuple[np.ndarray, Dict[str, int]]:
        """
        Remove edge artifacts and other unrealistic geometries.
        
        Args:
            seg_data: Segmentation data array
            
        Returns:
            Tuple of (cleaned_data, stats_dict)
        """
        cleaned_data = seg_data.copy()
        stats = {
            'edge_voxels_removed': 0,
            'total_cleaned': 0
        }
        
        # Remove segmentation on image edges (often artifacts)
        # Only remove if it's a very thin layer (1-2 voxels)
        edge_thickness = 2
        
        # Check each dimension
        for dim in range(3):
            # Remove from start of dimension
            edge_slice = [slice(None)] * 3
            edge_slice[dim] = slice(0, edge_thickness)
            edge_mask = np.zeros_like(cleaned_data, dtype=bool)
            edge_mask[tuple(edge_slice)] = True
            
            edge_voxels = np.count_nonzero(cleaned_data[edge_mask] > 0)
            if edge_voxels > 0:
                # Only remove if it's a small percentage of edge
                edge_ratio = edge_voxels / np.prod(cleaned_data[tuple(edge_slice)].shape)
                if edge_ratio < 0.1:  # Less than 10% of edge is segmented
                    cleaned_data[edge_mask & (cleaned_data > 0)] = 0
                    stats['edge_voxels_removed'] += edge_voxels
            
            # Remove from end of dimension
            edge_slice = [slice(None)] * 3
            edge_slice[dim] = slice(-edge_thickness, None)
            edge_mask = np.zeros_like(cleaned_data, dtype=bool)
            edge_mask[tuple(edge_slice)] = True
            
            edge_voxels = np.count_nonzero(cleaned_data[edge_mask] > 0)
            if edge_voxels > 0:
                edge_ratio = edge_voxels / np.prod(cleaned_data[tuple(edge_slice)].shape)
                if edge_ratio < 0.1:
                    cleaned_data[edge_mask & (cleaned_data > 0)] = 0
                    stats['edge_voxels_removed'] += edge_voxels
        
        stats['total_cleaned'] = stats['edge_voxels_removed']
        return cleaned_data, stats


def validate_and_clean(
    segmentation_img: nib.Nifti1Image,
    input_img: Optional[nib.Nifti1Image],
    label_dict: Dict[int, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main function to validate and optionally clean segmentation.
    
    Args:
        segmentation_img: Segmentation NIfTI image from Vista-3D
        input_img: Input NIfTI image (optional, for dimension comparison)
        label_dict: Dictionary mapping label IDs to label info
        config: Configuration dictionary with validation/cleanup settings
        
    Returns:
        Dictionary with validation results:
        - valid: bool - Overall validation status
        - warnings: List[str] - Non-blocking issues
        - errors: List[str] - Critical issues
        - stats: Dict - Statistics (voxel counts, label counts, etc.)
        - cleaned: bool - Whether cleanup was applied
        - cleaned_img: Optional[nib.Nifti1Image] - Cleaned image if cleanup applied
    """
    result = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'stats': {},
        'cleaned': False,
        'cleaned_img': None
    }
    
    seg_data = segmentation_img.get_fdata().astype(np.int16)
    total_voxels = seg_data.size
    
    # Initialize validator and cleaner
    validator = SegmentationValidator(config)
    cleaner = SegmentationCleaner(config)
    
    # Collect statistics
    unique_labels = np.unique(seg_data)
    unique_labels = unique_labels[unique_labels != 0]  # Remove background
    segmented_voxels = np.count_nonzero(seg_data)
    
    result['stats'] = {
        'total_voxels': total_voxels,
        'segmented_voxels': int(segmented_voxels),
        'segmentation_ratio': float(segmented_voxels / total_voxels) if total_voxels > 0 else 0.0,
        'num_labels': len(unique_labels),
        'label_ids': [int(label_id) for label_id in unique_labels]
    }
    
    # Run validations
    # 1. Dimension validation
    dim_valid, dim_errors = validator.validate_dimensions(segmentation_img, input_img)
    result['errors'].extend(dim_errors)
    
    # 2. Label validation
    label_valid, label_warnings, label_errors = validator.validate_labels(seg_data, label_dict)
    result['warnings'].extend(label_warnings)
    result['errors'].extend(label_errors)
    
    # 3. Voxel count validation
    voxel_valid, voxel_warnings, voxel_errors = validator.validate_voxel_counts(
        seg_data, label_dict, total_voxels
    )
    result['warnings'].extend(voxel_warnings)
    result['errors'].extend(voxel_errors)
    
    # 4. Spatial consistency validation
    spatial_valid, spatial_warnings, spatial_errors = validator.validate_spatial_consistency(seg_data)
    result['warnings'].extend(spatial_warnings)
    result['errors'].extend(spatial_errors)
    
    # 5. Statistical validation
    input_data = input_img.get_fdata() if input_img is not None else None
    stats_valid, stats_warnings, stats_errors = validator.validate_statistics(seg_data, input_data)
    result['warnings'].extend(stats_warnings)
    result['errors'].extend(stats_errors)
    
    # Determine overall validity
    result['valid'] = len(result['errors']) == 0
    
    # Apply cleanup if enabled and there are issues
    enable_cleanup = config.get('enable_cleanup', True)
    if enable_cleanup and (len(result['warnings']) > 0 or len(result['errors']) > 0):
        # Remove small components
        cleaned_data, num_removed = cleaner.remove_small_components(seg_data)
        
        # Clean artifacts
        cleaned_data, artifact_stats = cleaner.clean_artifacts(cleaned_data)
        
        if num_removed > 0 or artifact_stats['total_cleaned'] > 0:
            # Create cleaned image
            cleaned_img = nib.Nifti1Image(
                cleaned_data.astype(np.int16),
                segmentation_img.affine,
                segmentation_img.header
            )
            result['cleaned_img'] = cleaned_img
            result['cleaned'] = True
            result['stats']['components_removed'] = num_removed
            result['stats']['artifacts_removed'] = artifact_stats['total_cleaned']
    
    return result

