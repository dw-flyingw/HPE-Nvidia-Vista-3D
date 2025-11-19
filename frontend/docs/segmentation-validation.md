# Segmentation Validation and Cleanup

## Overview

The Vista-3D segmentation validation system provides automated quality checks and cleanup for segmentation outputs. This ensures that segmentations meet quality standards and helps identify potential issues before they affect downstream analysis.

## Features

- **Dimension Validation**: Ensures segmentation dimensions match the input image
- **Label Validation**: Detects unknown or invalid label IDs
- **Voxel Count Validation**: Validates voxel counts per label and overall segmentation ratios
- **Spatial Consistency Checks**: Identifies isolated components and noise
- **Statistical Validation**: Performs statistical analysis of segmentation quality
- **Automatic Cleanup**: Removes small components and edge artifacts

## Configuration

All validation settings are configured via environment variables in the `.env` file. The system defaults to **enabled** for both validation and cleanup.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SEGMENTATION_VALIDATION` | `true` | Enable/disable segmentation validation |
| `ENABLE_SEGMENTATION_CLEANUP` | `true` | Enable/disable automatic cleanup |
| `MIN_VOXELS_PER_LABEL` | `10` | Minimum voxels required per label (below this triggers warning) |
| `MIN_VOXELS_PER_COMPONENT` | `10` | Minimum voxels per connected component (smaller components are removed) |
| `MAX_SEGMENTATION_RATIO` | `0.95` | Maximum ratio of volume that can be segmented (prevents over-segmentation) |
| `MIN_SEGMENTATION_RATIO` | `0.001` | Minimum ratio of volume that should be segmented (detects under-segmentation) |

### Example `.env` Configuration

```bash
# Segmentation Validation Settings
ENABLE_SEGMENTATION_VALIDATION=true
ENABLE_SEGMENTATION_CLEANUP=true
MIN_VOXELS_PER_LABEL=10
MIN_VOXELS_PER_COMPONENT=10
MAX_SEGMENTATION_RATIO=0.95
MIN_SEGMENTATION_RATIO=0.001
```

### Disabling Validation

To disable validation entirely, set in your `.env` file:

```bash
ENABLE_SEGMENTATION_VALIDATION=false
```

To disable only cleanup (keep validation but don't auto-fix):

```bash
ENABLE_SEGMENTATION_CLEANUP=false
```

## Validation Checks

### 1. Dimension Validation

**Purpose**: Ensures segmentation matches input image dimensions and spatial properties.

**Checks**:
- Segmentation has valid 3D dimensions
- Shape matches input image (if available)
- Affine matrix matches input image (within tolerance)

**Errors**:
- Invalid dimensions (e.g., 2D instead of 3D)
- Dimension mismatch with input image
- Affine matrix mismatch

### 2. Label Validation

**Purpose**: Detects unknown or invalid label IDs in the segmentation.

**Checks**:
- All labels are present in the label dictionary
- No negative label IDs
- Valid label ID ranges

**Warnings**:
- Unknown label IDs found
- Labels not in expected dictionary

**Errors**:
- Negative label IDs (should not occur)

### 3. Voxel Count Validation

**Purpose**: Validates that segmentation has reasonable voxel counts and coverage.

**Checks**:
- Each label has minimum required voxels
- Overall segmentation ratio is within expected range
- No labels with suspiciously small voxel counts

**Warnings**:
- Labels with fewer than `MIN_VOXELS_PER_LABEL` voxels
- Segmentation covers > `MAX_SEGMENTATION_RATIO` of volume (over-segmentation)
- Segmentation covers < `MIN_SEGMENTATION_RATIO` of volume (under-segmentation)

### 4. Spatial Consistency Validation

**Purpose**: Detects isolated components and spatial artifacts.

**Checks**:
- Connected component analysis for each label
- Identification of small isolated components
- Detection of noise patterns

**Warnings**:
- Small isolated components detected (potential noise)
- Multiple disconnected regions for single label

### 5. Statistical Validation

**Purpose**: Performs statistical analysis to detect unusual patterns.

**Checks**:
- Empty segmentation detection
- Label distribution analysis
- Dominant label detection

**Errors**:
- Completely empty segmentation (only background)

**Warnings**:
- Single label dominates segmentation (>90% of segmented voxels)
- Unusual label distribution patterns

## Cleanup Operations

When cleanup is enabled, the system automatically fixes common issues:

### 1. Small Component Removal

**Operation**: Removes connected components smaller than `MIN_VOXELS_PER_COMPONENT`.

**Method**: Uses scipy's `ndimage.label` to identify connected components and removes those below the threshold.

**When Applied**: Automatically when small components are detected.

### 2. Artifact Removal

**Operation**: Removes edge artifacts and unrealistic geometries.

**Method**:
- Identifies segmentation on image edges (first/last 2 voxels)
- Removes edge segmentation if it represents <10% of edge voxels
- Prevents removal of legitimate edge structures

**When Applied**: Automatically when edge artifacts are detected.

## Usage

Validation runs automatically during segmentation processing. No additional steps are required.

### During Segmentation

When you run Vista-3D segmentation, validation output will appear in the console:

```
  Running segmentation validation...
  Validation Statistics:
    Labels found: 15
    Segmented voxels: 1,234,567
    Segmentation ratio: 45.23%
  ✅ Validation passed with no issues
```

### With Warnings

If issues are detected but not critical:

```
  Running segmentation validation...
  ⚠️  Validation Warnings (2):
    ⚠️  Found 3 label(s) with < 10 voxels: liver (ID: 1): 5 voxels, ...
    ⚠️  Found 5 small isolated component(s) (< 10 voxels each) - possible noise
  Validation Statistics:
    Labels found: 15
    Segmented voxels: 1,234,567
    Segmentation ratio: 45.23%
  ✅ Cleanup applied:
    Removed 5 small component(s)
    Removed 12 artifact voxel(s)
  ⚠️  Validation passed with warnings
```

### With Errors

If critical errors are found:

```
  Running segmentation validation...
  ⚠️  Validation Errors:
    ❌ Dimension mismatch: segmentation (512, 512, 200) != input (512, 512, 201)
  ❌ Validation failed with errors (continuing anyway)
```

**Note**: Even with errors, processing continues. The segmentation is still saved, but you should review the errors.

## Integration

The validation system is integrated into `utils/segment.py` and runs automatically:

1. **After segmentation loading**: Validation occurs after the segmentation is received from Vista-3D
2. **Before saving**: Validation and cleanup happen before the segmentation is saved to disk
3. **Non-blocking**: Validation errors don't stop processing (warnings are logged)

## Customization

### Adjusting Thresholds

You can adjust validation thresholds in your `.env` file:

```bash
# More strict validation (fewer false positives)
MIN_VOXELS_PER_LABEL=50
MIN_VOXELS_PER_COMPONENT=50
MIN_SEGMENTATION_RATIO=0.01

# More lenient validation (fewer false negatives)
MIN_VOXELS_PER_LABEL=5
MIN_VOXELS_PER_COMPONENT=5
MAX_SEGMENTATION_RATIO=0.98
```

### Programmatic Usage

You can also use the validation module programmatically:

```python
from utils.segmentation_validator import validate_and_clean
import nibabel as nib

# Load segmentation and input
seg_img = nib.load('segmentation.nii.gz')
input_img = nib.load('input.nii.gz')

# Load label dictionary
from utils.config_manager import ConfigManager
config_manager = ConfigManager()
label_dict = {item['id']: item for item in config_manager.label_colors}

# Configure validation
config = {
    'enable_cleanup': True,
    'min_voxels_per_label': 10,
    'min_voxels_per_component': 10,
    'max_segmentation_ratio': 0.95,
    'min_segmentation_ratio': 0.001
}

# Run validation
result = validate_and_clean(seg_img, input_img, label_dict, config)

# Check results
if result['valid']:
    print("Validation passed!")
    if result['cleaned']:
        print("Cleanup was applied")
        cleaned_img = result['cleaned_img']
        # Save cleaned image
        nib.save(cleaned_img, 'cleaned_segmentation.nii.gz')
else:
    print("Validation failed with errors:")
    for error in result['errors']:
        print(f"  - {error}")
```

## Troubleshooting

### Validation is Too Strict

If you're getting too many warnings:

1. Increase thresholds in `.env`:
   ```bash
   MIN_VOXELS_PER_LABEL=5
   MIN_VOXELS_PER_COMPONENT=5
   ```

2. Or disable specific checks by modifying the validation code.

### Validation is Too Lenient

If issues are being missed:

1. Decrease thresholds:
   ```bash
   MIN_VOXELS_PER_LABEL=20
   MIN_VOXELS_PER_COMPONENT=20
   ```

2. Adjust segmentation ratio thresholds:
   ```bash
   MAX_SEGMENTATION_RATIO=0.90
   MIN_SEGMENTATION_RATIO=0.01
   ```

### Cleanup Removing Valid Structures

If cleanup is too aggressive:

1. Disable cleanup:
   ```bash
   ENABLE_SEGMENTATION_CLEANUP=false
   ```

2. Or increase `MIN_VOXELS_PER_COMPONENT` to preserve larger structures.

### Performance Concerns

Validation adds minimal overhead:
- Dimension checks: <1ms
- Label validation: ~10-50ms
- Voxel count validation: ~50-200ms
- Spatial consistency: ~100-500ms (depends on image size)
- Cleanup: ~200-1000ms (depends on number of components)

For very large images (>1GB), consider:
- Disabling validation for batch processing
- Running validation only on problematic cases
- Adjusting thresholds to reduce processing time

## Technical Details

### Implementation

- **Module**: `utils/segmentation_validator.py`
- **Classes**: `SegmentationValidator`, `SegmentationCleaner`
- **Main Function**: `validate_and_clean()`
- **Dependencies**: `nibabel`, `numpy`, `scipy`

### Validation Flow

1. Load segmentation from Vista-3D
2. Load input image (if available)
3. Run all validation checks
4. Collect warnings and errors
5. Apply cleanup (if enabled and issues found)
6. Return validation results
7. Use cleaned image if cleanup was applied
8. Save segmentation

### Return Structure

The `validate_and_clean()` function returns a dictionary:

```python
{
    'valid': bool,              # Overall validation status
    'warnings': List[str],      # Non-blocking issues
    'errors': List[str],        # Critical issues
    'stats': Dict,              # Statistics (voxel counts, ratios, etc.)
    'cleaned': bool,            # Whether cleanup was applied
    'cleaned_img': Optional[Nifti1Image]  # Cleaned image if cleanup applied
}
```

## Best Practices

1. **Keep validation enabled** for production use
2. **Review warnings** regularly to identify patterns
3. **Adjust thresholds** based on your specific use case
4. **Monitor statistics** to understand segmentation quality trends
5. **Disable cleanup** if you need to manually review all issues
6. **Use validation results** to improve segmentation prompts/parameters

## Related Documentation

- [Configuration Guide](configuration.md) - General configuration options
- [Segmentation Guide](segmentation.md) - How to run Vista-3D segmentation
- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions

