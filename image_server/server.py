import os
import argparse
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, status, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import nibabel as nib
import numpy as np
import json
import tempfile

from dotenv import load_dotenv

load_dotenv()


def resolve_folder_path(env_var_name: str) -> str:
    folder_path = os.getenv(env_var_name)
    
    if not folder_path:
        raise ValueError(f"{env_var_name} must be set in .env file with full absolute path")
    
    if not os.path.isabs(folder_path):
        raise ValueError(f"{env_var_name} must be set in .env file with full absolute path, got: {folder_path}")
    return folder_path


output_folder = resolve_folder_path('OUTPUT_FOLDER')
dicom_folder = resolve_folder_path('DICOM_FOLDER')


def get_server_config():
    image_server_url = os.getenv("IMAGE_SERVER", "http://localhost:8888")
    parsed = urlparse(image_server_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8888
    return host, port


def load_image_server_config():
    script_dir = Path(__file__).parent
    config_path = script_dir / "conf" / "image_server_conf.json"

    default_config = {
        "viewable_folders": [
            {
                "name": "dicom",
                "path": dicom_folder,
                "url_path": "dicom",
                "description": "DICOM medical imaging files",
                "icon": "📁"
            },
            {
                "name": "output",
                "path": output_folder,
                "url_path": "output",
                "description": "Processed medical imaging output files",
                "icon": "📁"
            }
        ],
        "server_settings": {
            "title": "Medical Imaging Server",
            "description": "HTTP server for medical imaging files with directory browsing",
            "show_file_sizes": True,
            "show_hidden_files": False
        }
    }

    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)

            for folder in config.get("viewable_folders", []):
                if folder["name"] == "dicom":
                    folder["path"] = dicom_folder
                    folder["url_path"] = "dicom"
                elif folder["name"] == "output":
                    folder["path"] = output_folder
                    folder["url_path"] = "output"

            return config
        else:
            return default_config
    except Exception as e:
        print(f"Warning: Could not load image server config: {e}")
        return default_config


server_config = load_image_server_config()


def calculate_directory_size(directory_path: Path) -> int:
    """Recursively calculate total size of all files in directory and subdirectories."""
    total_size = 0
    try:
        for item in directory_path.iterdir():
            if item.name.startswith('.'):
                continue
            try:
                if item.is_file():
                    total_size += item.stat().st_size
                elif item.is_dir():
                    total_size += calculate_directory_size(item)
            except (PermissionError, OSError):
                # Skip files/directories we can't access
                continue
    except (PermissionError, OSError):
        pass
    return total_size


def generate_directory_listing(directory_path: Path, request_path: str) -> str:
    items = []
    server_settings = server_config.get("server_settings", {})
    dark_theme = server_settings.get("dark_theme", False)
    
    # Define theme colors
    if dark_theme:
        bg_color = "#1e1e1e"
        text_color = "#e0e0e0"
        heading_color = "#ffffff"
        border_color = "#444"
        header_bg = "#2d2d2d"
        link_color = "#58a6ff"
        meta_color = "#888"
        error_color = "#ff6b6b"
    else:
        bg_color = "#ffffff"
        text_color = "#333"
        heading_color = "#333"
        border_color = "#ddd"
        header_bg = "#f5f5f5"
        link_color = "#0066cc"
        meta_color = "#666"
        error_color = "#cc0000"
    
    # Calculate total size (including subdirectories) and counts
    total_size = calculate_directory_size(directory_path)
    file_count = 0
    dir_count = 0
    
    try:
        if request_path != "/":
            parent_path = str(Path(request_path).parent)
            if parent_path == ".":
                parent_path = "/"
            items.append(f'<li><a href="{parent_path}">📁 ../</a></li>')

        for item in sorted(directory_path.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                item_name = item.name
                item_path = f"{request_path.rstrip('/')}/{item_name}/"
                items.append(f'<li><a href="{item_path}">📁 {item_name}/</a></li>')
                dir_count += 1

        for item in sorted(directory_path.iterdir()):
            if item.is_file() and not item.name.startswith('.'):
                item_name = item.name
                item_path = f"{request_path.rstrip('/')}/{item_name}"
                file_size = item.stat().st_size
                file_count += 1
                size_str = f"({file_size:,} bytes)" if file_size < 1024*1024 else f"({file_size/(1024*1024):.1f} MB)"
                items.append(f'<li><a href="{item_path}">📄 {item_name}</a> <span class="meta">{size_str}</span></li>')

    except Exception as e:
        items.append(f'<li><span class="error">Error reading directory: {e}</span></li>')
    
    # Format total size
    if total_size < 1024:
        total_size_str = f"{total_size} bytes"
    elif total_size < 1024 * 1024:
        total_size_str = f"{total_size / 1024:.1f} KB"
    elif total_size < 1024 * 1024 * 1024:
        total_size_str = f"{total_size / (1024 * 1024):.1f} MB"
    else:
        total_size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"

    items_html = "\n".join(items)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Directory listing for {request_path}</title>
        <meta charset="utf-8">
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🩻</text></svg>">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; background-color: {bg_color}; color: {text_color}; }}
            h1 {{ color: {heading_color}; border-bottom: 1px solid {border_color}; padding-bottom: 10px; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin: 5px 0; }}
            a {{ text-decoration: none; color: {link_color}; }}
            a:hover {{ text-decoration: underline; }}
            .header {{ background: {header_bg}; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid {border_color}; color: {meta_color}; font-size: 0.9em; }}
            .meta {{ color: {meta_color}; font-size: 0.8em; }}
            .error {{ color: {error_color}; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📁 Directory listing for {request_path}</h1>
            <p>Image Server - Medical Imaging Files</p>
            <p class="meta">📊 {file_count} files, {dir_count} directories | Total size (including subdirectories): {total_size_str}</p>
        </div>
        <ul>
            {items_html}
        </ul>
        <div class="footer">
            <p>📥 Medical Imaging Server | FastAPI + Uvicorn</p>
        </div>
    </body>
    </html>
    """
    return html


server_settings = server_config.get("server_settings", {})
app = FastAPI(
    title=server_settings.get("title", "Medical Imaging Server"),
    description=server_settings.get("description", "HTTP server for medical imaging files with directory browsing")
)

# Mount assets if present
assets_dir = Path(__file__).parent / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "image-server"}


@app.get("/filtered-scans/{patient_id}/{filename}")
async def get_filtered_scans(
    patient_id: str,
    filename: str,
    label_ids: str = Query(..., description="Comma-separated list of label IDs to include")
):
    try:
        label_id_list = [int(id.strip()) for id in label_ids.split(',') if id.strip()]
        scan_path = Path(output_folder) / "scans" / patient_id / filename
        if not scan_path.exists():
            raise HTTPException(status_code=404, detail=f"Scan file not found: {filename}")
        nifti_img = nib.load(str(scan_path))
        data = nifti_img.get_fdata()
        filtered_data = np.zeros_like(data)
        for label_id in label_id_list:
            filtered_data[data == label_id] = label_id
        filtered_img = nib.Nifti1Image(filtered_data, nifti_img.affine, nifti_img.header)
        with tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False) as tmp_file:
            nib.save(filtered_img, tmp_file.name)
            def iter_file():
                with open(tmp_file.name, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
                os.unlink(tmp_file.name)
            return StreamingResponse(
                iter_file(),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename=filtered_{filename}",
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error filtering segmentation: {str(e)}")


@app.get("/filtered-scans/{patient_id}/voxels/{filename}")
async def get_filtered_voxels(
    patient_id: str,
    filename: str,
    label_ids: str = Query(..., description="Comma-separated list of label IDs to include")
):
    try:
        label_id_list = [int(id.strip()) for id in label_ids.split(',') if id.strip()]
        voxels_dir = Path(output_folder) / patient_id / "voxels"
        voxels_path = voxels_dir / filename
        if not voxels_path.exists():
            target_stem = Path(filename).stem
            candidates = []
            if voxels_dir.exists():
                for p in voxels_dir.iterdir():
                    if p.is_file() and p.suffix in (".nii", ".gz"):
                        candidates.append(p)
            chosen = None
            for p in candidates:
                if p.stem == target_stem:
                    chosen = p
                    break
            if chosen is None and candidates:
                chosen = candidates[0]
            if chosen is None:
                raise HTTPException(status_code=404, detail=f"Voxels file not found: {filename}")
            voxels_path = chosen

        nifti_img = nib.load(str(voxels_path))
        data = nifti_img.get_fdata()
        filtered_data = np.zeros_like(data)
        for label_id in label_id_list:
            filtered_data[data == label_id] = label_id
        filtered_img = nib.Nifti1Image(filtered_data, nifti_img.affine, nifti_img.header)
        with tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False) as tmp_file:
            nib.save(filtered_img, tmp_file.name)
            def iter_file():
                with open(tmp_file.name, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
                os.unlink(tmp_file.name)
            return StreamingResponse(
                iter_file(),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename=filtered_voxels_{filename}",
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error filtering voxels: {str(e)}")


@app.get("/output/{patient_id}/voxels/{filename}/labels")
async def get_available_voxel_labels(
    patient_id: str,
    filename: str,
):
    try:
        voxels_dir = Path(output_folder) / patient_id / "voxels"
        voxels_path = voxels_dir / filename
        if not voxels_path.exists():
            target_stem = Path(filename).stem
            candidates = []
            if voxels_dir.exists():
                for p in voxels_dir.iterdir():
                    if p.is_file() and p.suffix in (".nii", ".gz"):
                        candidates.append(p)
            chosen = None
            for p in candidates:
                if p.stem == target_stem:
                    chosen = p
                    break
            if chosen is None and candidates:
                chosen = candidates[0]
            if chosen is None:
                raise HTTPException(status_code=404, detail=f"Voxels file not found: {filename}")
            voxels_path = chosen

        nifti_img = nib.load(str(voxels_path))
        data = nifti_img.get_fdata()
        unique_vals = np.unique(data.astype(np.int32))
        label_ids = [int(v) for v in unique_vals if int(v) != 0]

        id_to_name = {}
        try:
            colors_path = Path(__file__).parent / ".." / "conf" / "vista3d_label_colors.json"
            colors_path = colors_path.resolve()
            if colors_path.exists():
                with open(colors_path, 'r') as f:
                    items = json.load(f)
                for item in items:
                    iid = int(item.get('id', -1))
                    name = item.get('name', '')
                    if iid >= 0:
                        id_to_name[iid] = name
        except Exception:
            pass

        labels = [{"id": lid, "name": id_to_name.get(lid, str(lid))} for lid in label_ids]
        return {"labels": labels, "voxel_filename": voxels_path.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading voxel labels: {str(e)}")


def is_allowed_directory(path: Path) -> bool:
    try:
        allowed_folder_paths = [Path(folder["path"]) for folder in server_config.get("viewable_folders", [])]
        if path == Path(output_folder) or path == Path(dicom_folder):
            return True
        for allowed_path in allowed_folder_paths:
            try:
                path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        try:
            for base_folder in [Path(output_folder), Path(dicom_folder)]:
                try:
                    rel_path = path.relative_to(base_folder)
                    path_parts = rel_path.parts
                    if path_parts:
                        allowed_url_paths = [folder["url_path"] for folder in server_config.get("viewable_folders", [])]
                        if path_parts[0] in allowed_url_paths:
                            return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False
    except Exception:
        return False


def generate_restricted_root_listing() -> HTMLResponse:
    items = []
    server_settings = server_config.get("server_settings", {})
    title = server_settings.get("title", "Medical Imaging Server")
    description = server_settings.get("description", "HTTP server for medical imaging files with directory browsing")
    dark_theme = server_settings.get("dark_theme", False)
    
    # Define theme colors
    if dark_theme:
        bg_color = "#1e1e1e"
        text_color = "#e0e0e0"
        heading_color = "#ffffff"
        border_color = "#444"
        header_bg = "#2d2d2d"
        link_color = "#58a6ff"
        meta_color = "#888"
    else:
        bg_color = "#ffffff"
        text_color = "#333"
        heading_color = "#333"
        border_color = "#ddd"
        header_bg = "#f5f5f5"
        link_color = "#0066cc"
        meta_color = "#666"
    
    for folder_config in server_config.get("viewable_folders", []):
        folder_name = folder_config.get("name", "")
        folder_path = folder_config.get("path", "")
        folder_url_path = folder_config.get("url_path", folder_name)
        folder_description = folder_config.get("description", "")
        folder_icon = folder_config.get("icon", "📁")
        full_path = Path(folder_path)
        if full_path.exists() and full_path.is_dir():
            items.append(f'<li><a href="/{folder_url_path}/">{folder_icon} {folder_name}/</a> <span class="meta">({folder_description})</span></li>')
    if not items:
        items.append('<li><span class="meta">No accessible folders found</span></li>')
    items_html = "\n".join(items)
    folder_names = [folder["name"] for folder in server_config.get("viewable_folders", [])]
    folder_list = ", ".join(folder_names) if folder_names else "none"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8">
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🩻</text></svg>">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; background-color: {bg_color}; color: {text_color}; }}
            h1 {{ color: {heading_color}; border-bottom: 1px solid {border_color}; padding-bottom: 10px; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin: 5px 0; }}
            a {{ text-decoration: none; color: {link_color}; }}
            a:hover {{ text-decoration: underline; }}
            .header {{ background: {header_bg}; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid {border_color}; color: {meta_color}; font-size: 0.9em; }}
            .meta {{ color: {meta_color}; font-size: 0.8em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📥 {title}</h1>
            <p>{description}</p>
            <p>Accessible folders: {folder_list}</p>
        </div>
        <ul>
            {items_html}
        </ul>
        <div class="footer">
            <p>📥 {title} | FastAPI + Uvicorn</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@app.get("/{full_path:path}")
@app.head("/{full_path:path}")
async def serve_files(request: Request, full_path: str):
    if full_path == "" or full_path == ".":
        return generate_restricted_root_listing()

    def map_url_to_actual_path(url_path: str) -> Path:
        for folder_config in server_config.get("viewable_folders", []):
            folder_url_path = folder_config.get("url_path", folder_config.get("name", ""))
            if url_path.startswith(folder_url_path + "/") or url_path == folder_url_path:
                actual_folder_path = Path(folder_config.get("path", ""))
                if url_path == folder_url_path:
                    return actual_folder_path
                else:
                    subpath = url_path[len(folder_url_path):].lstrip("/")
                    return actual_folder_path / subpath
        return Path(output_folder) / url_path

    absolute_path = map_url_to_actual_path(full_path)

    try:
        absolute_path = absolute_path.resolve()
        if not is_allowed_directory(absolute_path):
            raise HTTPException(status_code=403, detail="Access denied - only configured folders are accessible")
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")

    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    if absolute_path.is_file():
        return await serve_file_with_range(request, absolute_path)
    elif absolute_path.is_dir():
        request_path = "/" + full_path.strip("/")
        if request_path != "/" and not request_path.endswith("/"):
            request_path += "/"
        html_content = generate_directory_listing(absolute_path, request_path)
        return HTMLResponse(content=html_content, status_code=200)
    else:
        raise HTTPException(status_code=404, detail="Not found")


async def serve_file_with_range(request: Request, file_path: Path):
    import re
    file_size = file_path.stat().st_size
    range_header = request.headers.get('range')
    if not range_header:
        return FileResponse(
            file_path,
            headers={
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range"
            }
        )
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not range_match:
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")
    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")
    content_length = end - start + 1
    def iter_file_range():
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(8192, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
    return StreamingResponse(
        iter_file_range(),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range"
        },
        media_type="application/octet-stream"
    )


origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP Image Server")
    parser.add_argument("--host", help="Host to bind to (default: from IMAGE_SERVER env var)")
    parser.add_argument("--port", type=int, help="Port to bind to (default: from IMAGE_SERVER env var)")
    parser.add_argument("--disable-dir-listing", action="store_true", help="Disable directory listing")
    args = parser.parse_args()
    default_host, default_port = get_server_config()
    host = args.host or default_host
    port = args.port or default_port
    print(f"Starting HTTP Image Server with FastAPI/Uvicorn...")
    print(f"  URL: http://{host}:{port}")
    print(f"  Output Folder: {output_folder}")
    print(f"  DICOM Folder: {dicom_folder}")
    print(f"  Directory Listing Enabled: {not args.disable_dir_listing}")
    print(f"  CORS: Enabled for all origins")
    print(f"  Binding to: 0.0.0.0 (all interfaces)")
    print(f"  Press Ctrl+C to stop the server")
    print("-" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


