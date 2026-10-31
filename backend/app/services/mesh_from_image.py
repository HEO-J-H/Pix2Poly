"""
Build a watertight triangle mesh from a single image using a luminance heightfield.
This is a lightweight baseline (not learned single-view 3D); exports OBJ + GLB for download.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from PIL import Image


def heightfield_mesh(
    gray: np.ndarray,
    xy_scale: float = 1.0,
    height_scale: float = 0.45,
    rgb_arr: np.ndarray | None = None,
) -> trimesh.Trimesh:
    """Grid heightfield: X/Y in [-xy_scale, xy_scale], Z = gray * height_scale."""
    h, w = gray.shape
    if h < 2 or w < 2:
        raise ValueError("Image grid too small")

    z = gray * float(height_scale)
    verts: list[list[float]] = []
    for i in range(h):
        for j in range(w):
            x = (j / (w - 1)) * 2.0 * xy_scale - xy_scale
            y = (i / (h - 1)) * 2.0 * xy_scale - xy_scale
            verts.append([x, y, z[i, j]])
    v = np.asarray(verts, dtype=np.float64)

    faces: list[list[int]] = []
    for i in range(h - 1):
        for j in range(w - 1):
            idx = i * w + j
            # two triangles per quad; winding for +Z normal (right-hand, Y up in many viewers — adjust if needed)
            faces.append([idx, idx + w, idx + 1])
            faces.append([idx + 1, idx + w, idx + w + 1])

    mesh = trimesh.Trimesh(vertices=v, faces=np.asarray(faces, dtype=np.int64), process=False)
    # Avoid fix_normals() here (pulls scipy via graph); normals are fine for heightfield.
    if rgb_arr is not None:
        rgb_arr = np.asarray(rgb_arr)
        if rgb_arr.shape[:2] != (h, w) or rgb_arr.shape[2] < 3:
            raise ValueError("rgb_arr must be (h, w, 3+) matching grid")
        vc = np.zeros((v.shape[0], 4), dtype=np.uint8)
        for i in range(h):
            for j in range(w):
                idx = i * w + j
                vc[idx, 0] = int(rgb_arr[i, j, 0])
                vc[idx, 1] = int(rgb_arr[i, j, 1])
                vc[idx, 2] = int(rgb_arr[i, j, 2])
                vc[idx, 3] = 255
        mesh.visual = trimesh.visual.ColorVisuals(vertex_colors=vc)
    return mesh


def validate_image_input(image_bytes: bytes) -> None:
    """
    Validate image bytes for format and minimum resolution.
    Raises ValueError if empty, unreadable, or resolution is too low.
    """
    if not image_bytes:
        raise ValueError("Empty image input")
    try:
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        img.verify()
    except Exception as e:
        raise ValueError(f"Invalid image format: {e}") from e

    # Re-open after verify() closes/corrupts stream state for some formats
    try:
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        if width < 2 or height < 2:
            raise ValueError(f"Resolution too low ({width}x{height}); minimum 2x2 required")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read image dimensions: {e}") from e


def mesh_from_image_file(
    image_path: Path,
    output_dir: Path,
    grid: int = 200,
    height_scale: float = 0.45,
):
    """
    Read image from disk, validate, build mesh, write model.obj and model.glb under output_dir.
    Returns paths to obj and glb (absolute).
    """
    if not image_path.exists():
        raise ValueError(f"Image path does not exist: {image_path}")
    image_bytes = image_path.read_bytes()
    validate_image_input(image_bytes)

    output_dir.mkdir(parents=True, exist_ok=True)
    img_rgb = Image.open(image_path).convert("RGB").resize(
        (grid, grid), Image.Resampling.LANCZOS
    )
    gray = np.asarray(img_rgb.convert("L"), dtype=np.float64) / 255.0
    rgb_arr = np.asarray(img_rgb, dtype=np.uint8)
    mesh = heightfield_mesh(gray, height_scale=height_scale, rgb_arr=rgb_arr)

    obj_path = output_dir / "model.obj"
    glb_path = output_dir / "model.glb"
    mesh.export(str(obj_path))
    mesh.export(str(glb_path))
    return obj_path, glb_path
