"""
Multi-image 3D reconstruction via COLMAP SfM + MVS.

Pipeline:
  image_dir/
    → COLMAP feature_extractor
    → COLMAP exhaustive_matcher (sequential_matcher for video-like sets)
    → COLMAP mapper   → sparse/
    → COLMAP image_undistorter
    → COLMAP patch_match_stereo
    → COLMAP stereo_fusion  → fused.ply
    → Poisson mesh (Open3D) or trimesh ConvexHull fallback
    → OBJ + GLB

Environment variables:
  PIX2POLY_COLMAP_PATH  – path to colmap binary (default: "colmap")
  PIX2POLY_COLMAP_GPU   – "1" to enable GPU features (default: "0")

Requirements (installed separately):
  COLMAP: https://colmap.github.io/install.html
  open3d (optional, for Poisson mesh): pip install open3d
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _colmap_bin() -> str:
    env = os.environ.get("PIX2POLY_COLMAP_PATH", "").strip()
    if env and Path(env).is_file():
        return env
    found = shutil.which("colmap")
    if found:
        return found
    raise FileNotFoundError(
        "COLMAP binary not found. Install COLMAP and ensure it is on PATH, "
        "or set PIX2POLY_COLMAP_PATH."
    )


def _use_gpu() -> int:
    return 1 if os.environ.get("PIX2POLY_COLMAP_GPU", "0").strip() == "1" else 0


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1800,
    )
    if result.returncode != 0:
        out = result.stdout.decode(errors="replace")[-3000:]
        raise RuntimeError(f"COLMAP command failed ({cmd[1]}): {out}")


def run_colmap_sfm(
    image_dir: Path,
    work_dir: Path,
    sequential: bool = False,
) -> Path:
    """
    Run COLMAP SfM + MVS on a directory of images.

    Returns path to fused.ply (dense point cloud).
    work_dir is used for all intermediate files.
    """
    colmap = _colmap_bin()
    gpu = _use_gpu()
    db_path = work_dir / "database.db"
    sparse_dir = work_dir / "sparse"
    dense_dir = work_dir / "dense"
    sparse_dir.mkdir(parents=True, exist_ok=True)
    dense_dir.mkdir(parents=True, exist_ok=True)

    # 1. Feature extraction
    _run([
        colmap, "feature_extractor",
        "--database_path", str(db_path),
        "--image_path", str(image_dir),
        "--ImageReader.single_camera", "1",
        "--SiftExtraction.use_gpu", str(gpu),
    ], work_dir)

    # 2. Feature matching
    matcher = "sequential_matcher" if sequential else "exhaustive_matcher"
    _run([
        colmap, matcher,
        "--database_path", str(db_path),
        "--SiftMatching.use_gpu", str(gpu),
    ], work_dir)

    # 3. Sparse reconstruction (SfM mapper)
    _run([
        colmap, "mapper",
        "--database_path", str(db_path),
        "--image_path", str(image_dir),
        "--output_path", str(sparse_dir),
    ], work_dir)

    # Use first model (0) if multiple
    sparse_model = sparse_dir / "0"
    if not sparse_model.exists():
        # Try model without numeric subdirectory
        models = sorted(sparse_dir.iterdir())
        if not models:
            raise RuntimeError("COLMAP mapper produced no sparse model.")
        sparse_model = models[0]

    # 4. Image undistortion
    _run([
        colmap, "image_undistorter",
        "--image_path", str(image_dir),
        "--input_path", str(sparse_model),
        "--output_path", str(dense_dir),
        "--output_type", "COLMAP",
    ], work_dir)

    # 5. Dense stereo matching
    _run([
        colmap, "patch_match_stereo",
        "--workspace_path", str(dense_dir),
        "--workspace_format", "COLMAP",
        "--PatchMatchStereo.geom_consistency", "true",
        "--PatchMatchStereo.gpu_index", "-1" if gpu == 0 else "0",
    ], work_dir)

    # 6. Stereo fusion → fused.ply
    fused_ply = dense_dir / "fused.ply"
    _run([
        colmap, "stereo_fusion",
        "--workspace_path", str(dense_dir),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(fused_ply),
    ], work_dir)

    return fused_ply


def ply_to_mesh(ply_path: Path, out_dir: Path) -> tuple[Path, Path]:
    """
    Convert a point cloud .ply to a textured mesh using Open3D Poisson,
    falling back to trimesh ConvexHull if Open3D is not installed.
    Returns (obj_path, glb_path).
    """
    import numpy as np

    try:
        import open3d as o3d  # type: ignore

        pcd = o3d.io.read_point_cloud(str(ply_path))
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
        )
        pcd.orient_normals_consistent_tangent_plane(100)

        mesh_o3d, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=9
        )
        mesh_o3d = mesh_o3d.simplify_quadric_decimation(100_000)
        mesh_o3d.remove_degenerate_triangles()
        mesh_o3d.remove_duplicated_vertices()

        # Convert to trimesh
        import trimesh

        verts = np.asarray(mesh_o3d.vertices)
        faces = np.asarray(mesh_o3d.triangles)
        colors = None
        if mesh_o3d.has_vertex_colors():
            colors_o3d = np.asarray(mesh_o3d.vertex_colors)
            alpha = np.ones((len(colors_o3d), 1), dtype=np.float64)
            colors = np.clip(np.hstack([colors_o3d, alpha]) * 255, 0, 255).astype(np.uint8)

        tm = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        if colors is not None:
            tm.visual = trimesh.visual.ColorVisuals(vertex_colors=colors)

    except ImportError:
        # Fallback: load PLY with trimesh, build convex hull
        import trimesh

        pcd_tm = trimesh.load(str(ply_path))
        if hasattr(pcd_tm, "convex_hull"):
            tm = pcd_tm.convex_hull
        elif isinstance(pcd_tm, trimesh.PointCloud):
            tm = trimesh.convex.convex_hull(pcd_tm.vertices)
        else:
            tm = pcd_tm

    out_dir.mkdir(parents=True, exist_ok=True)
    obj_path = out_dir / "model.obj"
    glb_path = out_dir / "model.glb"
    tm.export(str(obj_path))
    tm.export(str(glb_path))
    return obj_path, glb_path


def run_colmap_pipeline(
    image_dir: Path,
    out_dir: Path,
    sequential: bool = False,
) -> tuple[Path, Path]:
    """
    End-to-end: images → COLMAP SfM+MVS → Poisson mesh → OBJ/GLB.
    Returns (obj_path, glb_path).
    """
    work_dir = out_dir / "_colmap_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        fused_ply = run_colmap_sfm(image_dir, work_dir, sequential=sequential)
        obj_abs, glb_abs = ply_to_mesh(fused_ply, out_dir)
    finally:
        # Clean up large intermediate files to save disk
        for pattern in ["*.bin", "*.dat"]:
            for f in work_dir.rglob(pattern):
                try:
                    f.unlink()
                except Exception:
                    pass
    return obj_abs, glb_abs


def colmap_available() -> bool:
    """True if COLMAP binary is found."""
    try:
        _colmap_bin()
        return True
    except FileNotFoundError:
        return False
