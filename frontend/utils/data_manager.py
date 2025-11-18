# frontend/utils/data_manager.py (Corrected)

import os
import re
import requests
from typing import List, Dict, Optional, Tuple, Set
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils.constants import SERVER_TIMEOUT

load_dotenv()

class DataManager:
    def __init__(self, image_server_url: str, force_external_url: bool = False):
        self.initial_image_server_url = image_server_url.rstrip('/')
        if force_external_url:
            self.image_server_url = self.initial_image_server_url
        else:
            self.image_server_url = self._find_working_image_server_url(self.initial_image_server_url)
        self.output_folder = os.getenv('OUTPUT_FOLDER')
        if not self.output_folder or not os.path.isabs(self.output_folder):
            raise ValueError("OUTPUT_FOLDER must be set as an absolute path in .env")

    def _find_working_image_server_url(self, initial_url: str) -> str:
        print(f"DEBUG: Using configured image server URL: {initial_url}")
        return initial_url

    def parse_directory_listing(self, html_content: str) -> List[Dict[str, str]]:
        """Parse HTML directory listing to extract file and folder information."""
        items = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # CHANGED: Find all <a> tags directly, which is more robust and works with the halverneus server.
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    # Extract name from href instead of text content to avoid emoji/icon issues
                    # href format: "/output/PA00000002/" or "/output/PA00000002/file.nii.gz"
                    href = href.strip()
                    
                    # Skip parent directory links
                    if href.endswith('../') or href == '..' or href.endswith('/../'):
                        continue
                    
                    # Extract the basename from the href path
                    # Remove leading/trailing slashes and get the last component
                    path_parts = [p for p in href.rstrip('/').split('/') if p]
                    if not path_parts:
                        continue
                    
                    clean_name = path_parts[-1]
                    is_directory = href.endswith('/')
                    
                    # Also skip if the name appears to be just an emoji/icon (contains only emoji/special chars)
                    # This is a safety check, but extracting from href should already avoid this
                    if not clean_name or clean_name.strip() == '':
                        continue

                    items.append({
                        'name': clean_name,
                        'is_directory': is_directory,
                        'size_bytes': 0, # This server doesn't provide size info in the listing
                        'size_display': "N/A"
                    })
        except Exception as e:
            print(f"Error parsing directory listing: {e}")
        return items

    def get_folder_contents(self, folder_path: str) -> Optional[List[Dict[str, str]]]:
        """Fetch contents of a specific folder from the image server."""
        # The new fileserver serves from its root, so the URL path matches the file path
        url_path = folder_path.strip('/')
        url = f"{self.image_server_url}/{url_path}" if url_path else self.image_server_url
        
        try:
            response = requests.get(url, timeout=SERVER_TIMEOUT)
            if response.status_code == 200:
                return self.parse_directory_listing(response.text)
            elif response.status_code != 404:
                print(f"Image server returned HTTP {response.status_code} for URL: {url}")
        except requests.exceptions.RequestException as e:
            print(f"Could not connect to image server at {url}: {e}")
        return None

    def get_server_data(self, path: str, data_type: str, file_extensions: tuple) -> List[str]:
        """Get folders or files from the server based on path and type."""
        # For the root patient listing, the path is 'output'
        # For scans, the path is 'output/PATIENT_ID/nifti'
        full_path = os.path.join('output', path) if path else 'output'
        items = self.get_folder_contents(full_path)
        
        if items is None:
            return []

        if data_type == 'folders':
            return sorted([item['name'] for item in items if item['is_directory']])
        elif data_type == 'files':
            return sorted([
                item['name'] for item in items
                if not item['is_directory'] and item['name'].lower().endswith(file_extensions)
            ])
        return []

    # ... The rest of the functions in this class remain the same ...
    def fetch_available_voxel_labels(
        self,
        patient_id: str,
        filename: str,
        filename_to_id_mapping: Dict[str, int]
    ) -> Tuple[Set[int], Dict[int, str]]:
        if not patient_id or not filename:
            return set(), {}
        try:
            ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '')
            voxels_folder_url = f"{self.image_server_url}/output/{patient_id}/voxels/{ct_scan_folder_name}/"
            resp = requests.get(voxels_folder_url, timeout=SERVER_TIMEOUT)
            if resp.status_code != 200:
                return set(), {}
            soup = BeautifulSoup(resp.text, 'html.parser')
            voxel_files = [link.get('href') for link in soup.find_all('a') if link.get('href') and link.get('href').endswith('.nii.gz')]
            # Extract just the filename from the href (handle both relative and absolute paths)
            available_filenames = {f.split('/')[-1] for f in voxel_files if f.split('/')[-1] in filename_to_id_mapping}
            available_ids = {filename_to_id_mapping[fname] for fname in available_filenames}
            # Return mapping from label_id to filename (with .nii.gz extension) for use in URL construction
            id_to_path_map = {label_id: fname for fname, label_id in filename_to_id_mapping.items() if label_id in available_ids}
            return available_ids, id_to_path_map
        except Exception as e:
            print(f"Error fetching available voxel labels: {e}")
            return set(), {}