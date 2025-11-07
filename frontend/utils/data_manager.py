"""
Data Manager for Vista3D Application
Handles all server interactions and data fetching operations.
"""

import os
import re
from urllib.parse import urlparse, urljoin
import requests
from typing import List, Dict, Optional, Tuple, Set
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils.constants import SERVER_TIMEOUT

# Load environment variables
load_dotenv()


class DataManager:
    """
    Handles all interactions with the image server.
    Provides methods for fetching directory listings, files, and voxel information.
    """

    def __init__(self, image_server_url: str, force_external_url: bool = False):
        self.initial_image_server_url = image_server_url.rstrip('/')
        
        # If this is for external access (browser), don't try to find working URLs
        if force_external_url:
            self.image_server_url = self.initial_image_server_url
        else:
            self.image_server_url = self._find_working_image_server_url(self.initial_image_server_url)
        
        # Get output folder from environment - must be absolute path
        self.output_folder = os.getenv('OUTPUT_FOLDER')
        if not self.output_folder:
            raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")
        if not os.path.isabs(self.output_folder):
            raise ValueError("OUTPUT_FOLDER must be set in .env file with absolute path")

    def _find_working_image_server_url(self, initial_url: str) -> str:
        """
        Attempts to find a working image server URL by trying multiple fallbacks.
        """
        urls_to_try = [initial_url]
        
        # If running in Docker container, try multiple approaches
        if os.getenv("DOCKER_CONTAINER") == "true":
            # Add Docker-specific fallbacks
            urls_to_try.extend([
                "http://localhost:8888",  # localhost fallback
                "http://127.0.0.1:8888",  # IP fallback
                "http://image-server:8888",  # Container name (if image server is in same compose)
            ])
        
        # Ensure unique URLs and preserve order as much as possible
        unique_urls = []
        for url in urls_to_try:
            if url not in unique_urls:
                unique_urls.append(url)

        print(f"DEBUG: Attempting to connect to image server using URLs: {unique_urls}")

        for url in unique_urls:
            try:
                # Try to access a known endpoint, like the root of the output directory
                test_url = f"{url}/output/"
                response = requests.head(test_url, timeout=SERVER_TIMEOUT)
                if response.status_code == 200:
                    print(f"DEBUG: Successfully connected to image server at: {url}")
                    return url
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                print(f"DEBUG: Connection attempt to {url} failed: {type(e).__name__}: {e}")
                continue
        
        print(f"DEBUG: Failed to connect to image server using any of the fallback URLs. Defaulting to initial URL: {initial_url}")
        return initial_url # Fallback to the initial URL if no working URL is found


    def parse_directory_listing(self, html_content: str) -> List[Dict[str, str]]:
        """Parse HTML directory listing to extract file and folder information."""
        items = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for item in soup.find_all('li'):
                link = item.find('a')
                if link and link.get('href'):
                    text = link.get_text().strip()
                    if text == "📁 ../" or text.endswith('../'):
                        continue
                    is_directory = text.startswith('📁') or text.endswith('/')
                    name = re.sub(r'^📁\s*|📄\s*', '', text).strip('/')
                    
                    # Extract file size from the span element
                    size_bytes = 0
                    size_display = "N/A"
                    if not is_directory:
                        # Look for size span element after the link
                        size_span = item.find('span')
                        if size_span:
                            size_text = size_span.get_text().strip()
                            # Parse size text like "(39.2 MB)" or "(1,638 bytes)"
                            size_match = re.search(r'\(([0-9,]+\.?[0-9]*)\s*(bytes|KB|MB|GB|TB)\)', size_text)
                            if size_match:
                                size_value = float(size_match.group(1).replace(',', ''))
                                size_unit = size_match.group(2)
                                
                                # Convert to bytes
                                if size_unit == 'bytes':
                                    size_bytes = int(size_value)
                                elif size_unit == 'KB':
                                    size_bytes = int(size_value * 1024)
                                elif size_unit == 'MB':
                                    size_bytes = int(size_value * 1024 * 1024)
                                elif size_unit == 'GB':
                                    size_bytes = int(size_value * 1024 * 1024 * 1024)
                                elif size_unit == 'TB':
                                    size_bytes = int(size_value * 1024 * 1024 * 1024 * 1024)
                                
                                size_display = size_text.strip('()')
                    
                    items.append({
                        'name': name, 
                        'is_directory': is_directory,
                        'size_bytes': size_bytes,
                        'size_display': size_display
                    })
        except Exception as e:
            print(f"Error parsing directory listing: {e}")
        return items

    def get_folder_contents(self, folder_path: str) -> Optional[List[Dict[str, str]]]:
        """Fetch contents of a specific folder from the image server."""
        # Use the URL path 'output' instead of the absolute path
        url = f"{self.image_server_url}/output/{folder_path.strip('/')}/"
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
        items = self.get_folder_contents(path)
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

    def fetch_available_voxel_labels(
        self,
        patient_id: str,
        filename: str,
        filename_to_id_mapping: Dict[str, int]
    ) -> Tuple[Set[int], Dict[int, str]]:
        """
        Query image server for available voxel files.
        Returns (available_label_ids, id_to_name_map).
        Folder structure: output/patient/voxels/scan_name/
        """
        if not patient_id or not filename:
            return set(), {}

        try:
            # Folder structure: /output/patient/voxels/scan_name/
            ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '')

            voxels_folder_url = f"{self.image_server_url}/output/{patient_id}/voxels/{ct_scan_folder_name}/"
            print(f"DEBUG: Using voxel directory: {voxels_folder_url}")

            def collect_voxel_files(url: str, depth: int = 0, visited: Set[str] = None) -> List[str]:
                """Recursively collect voxel files from directory listings."""
                if visited is None:
                    visited = set()

                normalized_url = url.rstrip('/') + '/' if not url.endswith('/') else url
                if normalized_url in visited:
                    return []
                visited.add(normalized_url)

                try:
                    resp_inner = requests.get(normalized_url, timeout=SERVER_TIMEOUT)
                except requests.RequestException as exc:  # pragma: no cover - defensive logging
                    print(f"DEBUG: Error accessing {normalized_url}: {exc}")
                    return []

                print(f"DEBUG: [{depth}] Response status for {normalized_url}: {resp_inner.status_code}")
                if resp_inner.status_code != 200:
                    return []

                soup_inner = BeautifulSoup(resp_inner.text, 'html.parser')
                files: List[str] = []
                for link in soup_inner.find_all('a'):
                    href = link.get('href')
                    if not href or href.startswith('..'):
                        continue
                    if href.endswith('.nii.gz'):
                        file_url = href if href.startswith('http') else urljoin(normalized_url, href)
                        files.append(file_url)
                    elif href.endswith('/'):
                        # Explore subdirectories (e.g., "original/")
                        child_url = urljoin(normalized_url, href)
                        files.extend(collect_voxel_files(child_url, depth + 1, visited))
                return files

            voxel_files = collect_voxel_files(voxels_folder_url)
            # Remove duplicates while preserving order
            if voxel_files:
                voxel_files = list(dict.fromkeys(voxel_files))

            # Convert file URLs to paths relative to the scan folder
            base_path = urlparse(voxels_folder_url).path
            normalized_base_path = base_path if base_path.endswith('/') else f"{base_path}/"
            relative_voxel_paths: List[str] = []
            for file_url in voxel_files:
                parsed_path = urlparse(file_url).path
                if parsed_path.startswith(normalized_base_path):
                    relative_path = parsed_path[len(normalized_base_path):].lstrip('/')
                else:
                    relative_path = parsed_path.split('/')[-1]
                relative_voxel_paths.append(relative_path)

            if __debug__:
                print(f"DEBUG: Found {len(relative_voxel_paths)} voxel files: {relative_voxel_paths}")

            # Find which label IDs are available based on existing voxel files
            available_ids = set()
            matched_files = []
            id_to_filename: Dict[int, str] = {}
            for relative_path in relative_voxel_paths:
                # Extract just the filename from the full path
                filename_only = relative_path.split('/')[-1]
                if filename_only in filename_to_id_mapping:
                    label_id = filename_to_id_mapping[filename_only]
                    available_ids.add(label_id)
                    matched_files.append(filename_only)
                    id_to_filename[label_id] = relative_path

            if __debug__:
                print(f"DEBUG: Matched {len(matched_files)} files to label IDs: {matched_files}")
                print(f"DEBUG: Available label IDs: {available_ids}")

            # Create id_to_name mapping for available labels
            # Use the actual relative file paths for precise overlay loading
            return available_ids, id_to_filename

        except Exception as e:
            print(f"Error fetching available voxel labels: {e}")
            return set(), {}

    def get_voxel_directory_url(self, patient_id: str, filename: str) -> str:
        """Generate the URL for the voxel directory."""
        ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '') if filename else ''
        return f"{self.image_server_url}/output/{patient_id}/voxels/{ct_scan_folder_name}/"
    
    def get_ply_directory_url(self, patient_id: str, filename: str) -> str:
        """Generate the URL for the PLY directory."""
        ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '') if filename else ''
        return f"{self.image_server_url}/output/{patient_id}/ply/{ct_scan_folder_name}/"
    
    def get_obj_directory_url(self, patient_id: str, scan_name: str) -> str:
        """Generate the URL for the OBJ directory."""
        return f"{self.image_server_url}/output/{patient_id}/obj/{scan_name}/"
    
    def get_obj_scans(self, patient_id: str) -> List[str]:
        """Get list of scan folders containing OBJ files for a patient."""
        obj_folders = self.get_server_data(f"{patient_id}/obj", 'folders', ('',))
        return sorted(obj_folders) if obj_folders else []
    
    def get_obj_files(self, patient_id: str, scan_name: str) -> List[str]:
        """Get list of OBJ files for a specific patient and scan."""
        obj_files = self.get_server_data(f"{patient_id}/obj/{scan_name}", 'files', ('.obj',))
        return sorted(obj_files) if obj_files else []
    
    def get_file_url(self, patient_id: str, file_path: str) -> str:
        """Generate the full URL for a file within a patient's directory."""
        return f"{self.image_server_url}/output/{patient_id}/{file_path}"

    def _find_voxel_directory(self, patient_id: str, filename: str) -> Optional[str]:
        """
        Find the correct voxel directory for a given patient and file.
        Returns the full URL to the voxel directory, or None if not found.
        """
        # First try the filename-based approach
        ct_scan_folder_name = filename.replace('.nii.gz', '').replace('.nii', '')
        voxels_folder_url = f"{self.image_server_url}/output/{patient_id}/voxels/{ct_scan_folder_name}/"
        
        print(f"DEBUG: Trying filename-based voxel directory: {voxels_folder_url}")
        
        try:
            resp = requests.get(voxels_folder_url, timeout=SERVER_TIMEOUT)
            if resp.status_code == 200:
                # Check if this directory actually contains .nii.gz files
                soup = BeautifulSoup(resp.text, 'html.parser')
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href and href.endswith('.nii.gz') and not href.startswith('..'):
                        print(f"DEBUG: Found voxel files in filename-based directory")
                        return voxels_folder_url
        except Exception as e:
            print(f"DEBUG: Error checking filename-based directory: {e}")
        
        # If filename-based approach fails, try to find available voxel directories
        parent_voxels_url = f"{self.image_server_url}/output/{patient_id}/voxels/"
        print(f"DEBUG: Checking parent voxels directory: {parent_voxels_url}")
        
        try:
            parent_resp = requests.get(parent_voxels_url, timeout=SERVER_TIMEOUT)
            if parent_resp.status_code == 200:
                parent_soup = BeautifulSoup(parent_resp.text, 'html.parser')
                available_dirs = []
                for link in parent_soup.find_all('a'):
                    href = link.get('href')
                    if href and not href.startswith('..') and href.endswith('/'):
                        available_dirs.append(href.rstrip('/'))
                
                print(f"DEBUG: Available voxel directories: {available_dirs}")
                
                if len(available_dirs) == 1:
                    # If there's only one voxel directory, use it
                    voxel_dir = available_dirs[0]
                    voxel_url = f"{parent_voxels_url}{voxel_dir}/"
                    print(f"DEBUG: Using single available voxel directory: {voxel_url}")
                    
                    # Verify it contains .nii.gz files
                    dir_resp = requests.get(voxel_url, timeout=SERVER_TIMEOUT)
                    if dir_resp.status_code == 200:
                        dir_soup = BeautifulSoup(dir_resp.text, 'html.parser')
                        for link in dir_soup.find_all('a'):
                            href = link.get('href')
                            if href and href.endswith('.nii.gz') and not href.startswith('..'):
                                return voxel_url
                
                elif len(available_dirs) > 1:
                    # Multiple directories - for now, try to find one that contains voxel files
                    # This could be enhanced with better matching logic in the future
                    for voxel_dir in available_dirs:
                        voxel_url = f"{parent_voxels_url}{voxel_dir}/"
                        try:
                            dir_resp = requests.get(voxel_url, timeout=SERVER_TIMEOUT)
                            if dir_resp.status_code == 200:
                                dir_soup = BeautifulSoup(dir_resp.text, 'html.parser')
                                voxel_count = 0
                                for link in dir_soup.find_all('a'):
                                    href = link.get('href')
                                    if href and href.endswith('.nii.gz') and not href.startswith('..'):
                                        voxel_count += 1
                                
                                if voxel_count > 0:
                                    print(f"DEBUG: Found {voxel_count} voxel files in directory {voxel_dir}")
                                    return voxel_url
                        except Exception as e:
                            print(f"DEBUG: Error checking directory {voxel_dir}: {e}")
                            continue
                
                print(f"DEBUG: No suitable voxel directory found")
                return None
            else:
                print(f"DEBUG: Failed to access parent voxels directory. Status: {parent_resp.status_code}")
                return None
                
        except Exception as e:
            print(f"DEBUG: Error accessing parent voxels directory: {e}")
            return None