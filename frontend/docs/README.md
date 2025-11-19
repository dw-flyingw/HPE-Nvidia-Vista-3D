# HPE-NVIDIA Vista-3D Frontend Documentation

Welcome to the documentation for the HPE-NVIDIA Vista-3D Frontend application.

## Documentation Index

### User Guides

- [Segmentation Validation and Cleanup](segmentation-validation.md) - Quality checks and automatic cleanup for Vista-3D segmentations

### Configuration

- [Environment Variables](configuration.md) - Complete list of environment variables and configuration options

### Development

- [Architecture Overview](architecture.md) - System architecture and component overview
- [API Reference](api-reference.md) - API documentation for developers

## Quick Start

1. **Setup**: Run `python setup.py` to configure your environment
2. **Configuration**: Edit `.env` file with your paths and settings
3. **Run**: Start the application with `streamlit run app.py`

## Key Features

- **DICOM to NIfTI Conversion**: Convert DICOM files to NIfTI format
- **Vista-3D Segmentation**: Run AI-powered segmentation on medical images
- **3D Visualization**: Interactive 3D viewer with NiiVue
- **Quality Validation**: Automatic validation and cleanup of segmentation outputs

## Getting Help

- Check the [Troubleshooting Guide](troubleshooting.md) for common issues
- Review the [Segmentation Validation](segmentation-validation.md) guide for quality checks
- See [Configuration](configuration.md) for all available options

## Contributing

When adding new features:
1. Update relevant documentation
2. Add examples if applicable
3. Update this README if adding new major features

