"""
Configuration Manager for Vista3D Application
Handles loading and caching of configuration files to avoid repeated I/O operations.
"""

import hashlib
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path


class ConfigManager:
    """
    Centralized configuration management for Vista3D application.
    Caches JSON configuration files to avoid repeated file I/O.
    """

    def __init__(self, config_dir: str = "conf"):
        self.config_dir = Path(config_dir)
        self._label_colors: Optional[List[Dict[str, Any]]] = None
        self._label_dict: Optional[Dict[str, int]] = None
        self._label_sets: Optional[Dict[str, Any]] = None
        self._using_fallback_label_colors: bool = False

    @property
    def label_colors(self) -> List[Dict[str, Any]]:
        """Load and cache label colors configuration."""
        if self._label_colors is None:
            label_colors = self._load_json("vista3d_label_colors.json")
            if label_colors:
                self._label_colors = label_colors
                self._using_fallback_label_colors = False
            else:
                self._label_colors = self._generate_default_label_colors()
                self._using_fallback_label_colors = True
                print("Warning: Using generated fallback colors for anatomical labels - conf/vista3d_label_colors.json was not found")
        return self._label_colors or []

    @property
    def label_dict(self) -> Dict[str, int]:
        """Load and cache label dictionary configuration."""
        if self._label_dict is None:
            self._label_dict = self._load_json("vista3d_label_dict.json")
        return self._label_dict or {}

    @property
    def label_sets(self) -> Dict[str, Any]:
        """Load and cache label sets configuration."""
        if self._label_sets is None:
            self._label_sets = self._load_json("vista3d_label_sets.json")
        return self._label_sets or {}

    def _load_json(self, filename: str) -> Optional[Any]:
        """Load JSON file from config directory."""
        file_path = self.config_dir / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load {filename}: {e}")
            return None

    def get_label_color(self, label_id: int) -> Optional[List[int]]:
        """Get RGB color for a specific label ID."""
        for item in self.label_colors:
            if item.get('id') == label_id:
                return item.get('color')
        return None

    def get_label_name(self, label_id: int) -> Optional[str]:
        """Get name for a specific label ID."""
        for item in self.label_colors:
            if item.get('id') == label_id:
                return item.get('name')
        return None

    def get_label_id(self, label_name: str) -> Optional[int]:
        """Get label ID for a specific label name."""
        return self.label_dict.get(label_name)

    def create_filename_to_id_mapping(self) -> Dict[str, int]:
        """Create mapping from expected filenames to label IDs."""
        filename_to_id = {}
        for label_name, label_id in self.label_dict.items():
            if label_id is None:
                continue
            # Skip background label (0) - there is no voxel file for it
            if int(label_id) == 0:
                continue

            expected_filename = label_name.lower().replace(' ', '_').replace('-', '_') + '.nii.gz'
            filename_to_id[expected_filename] = int(label_id)
        return filename_to_id

    def refresh_cache(self):
        """Force reload all cached configurations."""
        self._label_colors = None
        self._label_dict = None
        self._label_sets = None

    def _generate_default_label_colors(self) -> List[Dict[str, Any]]:
        """Generate deterministic fallback colors when label colors config is missing."""
        generated_colors: List[Dict[str, Any]] = []
        label_dict = self.label_dict

        if not label_dict:
            return generated_colors

        # Sort by label ID for deterministic ordering
        for name, label_id in sorted(label_dict.items(), key=lambda item: item[1]):
            if label_id == 0:
                color = [0, 0, 0]
            else:
                # Generate pseudo-random but deterministic bright colors per label name
                digest = hashlib.sha1(name.encode('utf-8')).digest()
                color = [64 + digest[0] % 192, 64 + digest[1] % 192, 64 + digest[2] % 192]

            generated_colors.append({
                "id": label_id,
                "name": name,
                "color": color
            })

        return generated_colors
