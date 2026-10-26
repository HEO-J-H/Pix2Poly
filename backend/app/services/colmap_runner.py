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


REPO_ROOT = Path(__file__).resolve().parents[3]
# scripts/install-colmap.bat 이 공식 릴리스를 여기에 풀어 둠 (COLMAP.bat 이 DLL 경로를 잡아 줌)
BUNDLED = (REPO_ROOT / "colmap" / "COLMAP.bat", REPO_ROOT / "colmap" / "bin" / "colmap.exe")


def _colmap_bin() -> str:
    env = os.environ.get("PIX2POLY_COLMAP_PATH", "").strip()
    if env and Path(env).is_file():
        return env
    for b in BUNDLED:
        if b.is_file():
            return str(b)
    found = shutil.which("colmap")
    if found:
        return found
    raise FileNotFoundError(
        "COLMAP binary not found. Install COLMAP and ensure it is on PATH, "
        "or set PIX2POLY_COLMAP_PATH."
    )


_CUDA: bool | None = None


def colmap_has_cuda() -> bool:
    """COLMAP 이 CUDA 빌드인지 (-h 첫 줄에 'with CUDA' / 'without CUDA'). 정밀(dense) 복원은 CUDA 필요."""
    global _CUDA
    if _CUDA is None:
        try:
            out = subprocess.run([_colmap_bin(), "-h"], capture_output=True, timeout=30).stdout.decode(errors="replace")
            _CUDA = "with CUDA" in out
        except (OSError, subprocess.SubprocessError, FileNotFoundError):
            _CUDA = False
    return _CUDA


def _use_gpu() -> int:
    env = os.environ.get("PIX2POLY_COLMAP_GPU", "").strip()
    if env in ("0", "1"):
        return int(env)
    return 1 if colmap_has_cuda() else 0


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
    mask_dir: Path | None = None,
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
        *(["--ImageReader.mask_path", str(mask_dir)] if mask_dir else []),
        "--FeatureExtraction.use_gpu", str(gpu),
    ], work_dir)

    # 2. Feature matching
    matcher = "sequential_matcher" if sequential else "exhaustive_matcher"
    _run([
        colmap, matcher,
        "--database_path", str(db_path),
        "--FeatureMatching.use_gpu", str(gpu),
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

    if not gpu:  # CUDA 없는 PC: 정밀 복원 불가 → 희소 점으로 대략적인 형태만
        sparse_ply = work_dir / "sparse.ply"
        _run([colmap, "model_converter", "--input_path", str(sparse_model),
              "--output_path", str(sparse_ply), "--output_type", "PLY"], work_dir)
        return sparse_ply

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

    # 1순위: COLMAP 내장 poisson_mesher (추가 설치 없음)
    try:
        meshed = ply_path.with_name("meshed-poisson.ply")
        _run([_colmap_bin(), "poisson_mesher", "--input_path", str(ply_path), "--output_path", str(meshed),
              "--PoissonMeshing.trim", "7"], ply_path.parent)
        import trimesh
        tm = trimesh.load(str(meshed), process=False)
        if len(getattr(tm, "faces", [])) > 0:
            out_dir.mkdir(parents=True, exist_ok=True)
            obj_path, glb_path = out_dir / "model.obj", out_dir / "model.glb"
            tm.export(str(obj_path))
            tm.export(str(glb_path))
            return obj_path, glb_path
    except (RuntimeError, FileNotFoundError, OSError, ValueError, ImportError):
        pass

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


MIN_POINTS = 1500  # 이보다 적으면 메시가 뭉개진 덩어리 — 결과 대신 이유를 알려 줌


def _ply_vertex_count(path: Path) -> int:
    with open(path, "rb") as f:
        for line in f:
            if line.startswith(b"element vertex"):
                return int(line.split()[-1])
            if line.startswith(b"end_header"):
                break
    return 0


MVS_DIR = REPO_ROOT / "openmvs"  # scripts/install-colmap.bat 이 OpenMVS(AGPL)를 여기에 — 별도 실행 파일로만 호출


def openmvs_available() -> bool:
    return (MVS_DIR / "TextureMesh.exe").is_file() and (MVS_DIR / "InterfaceCOLMAP.exe").is_file()


TEXTURE_FACES = (30000, 25000, 40000)  # 잘게 쪼갠 메시는 색이 노이즈처럼 입혀지고 OpenMVS 가 종종 비정상 종료 → 줄여서 시도
MAX_BLACK_SHARE = 0.25                  # 텍스처의 검은(색 못 찾은) 부분이 이보다 많으면 정점 색 메시를 대신 사용


def _black_share(tex: Path) -> float:
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(tex).convert("RGB")).astype(int)
    empty = (abs(a[..., 0] - 255) < 20) & (abs(a[..., 1] - 127) < 30) & (a[..., 2] < 60)  # OpenMVS 빈칸(주황)
    used = ~empty
    return float(((a.sum(2) < 30) & used).sum() / max(1, used.sum()))


def texture_mesh(dense_dir: Path, mesh_ply: Path, out_dir: Path) -> tuple[Path, Path] | None:
    """COLMAP 정밀 복원 결과(왜곡 보정된 사진·카메라)로 메시에 사진 색을 입힘 (OpenMVS TextureMesh).
    성공·품질 통과면 (obj, glb), 아니면 None (정점 색 메시 유지)."""
    if not openmvs_available():
        return None
    import trimesh
    work = dense_dir.parent / "mvs"
    work.mkdir(parents=True, exist_ok=True)
    try:
        _run([str(MVS_DIR / "InterfaceCOLMAP.exe"), "-i", str(dense_dir), "-o", str(work / "scene.mvs"),
              "--image-folder", str(dense_dir / "images"), "-w", str(work)], work)
        for f in work.glob("depth*.dmap"):  # 깊이맵을 쓰면 가림 판정이 어긋나 검게 칠해지는 면이 많음
            f.unlink()
        src = trimesh.load(str(mesh_ply), process=False)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
        return None
    for n in TEXTURE_FACES:
        try:
            small = work / f"mesh{n}.ply"
            (src.simplify_quadric_decimation(face_count=n) if len(src.faces) > n else src).export(str(small))
            for f in work.glob("textured*"):
                f.unlink()
            _run([str(MVS_DIR / "TextureMesh.exe"), str(work / "scene.mvs"), "-m", str(small),
                  "-o", str(work / "textured.obj"), "--export-type", "obj", "-w", str(work)], work)
            obj = work / "textured.obj"
            tex = next(work.glob("textured*_map_Kd.*"), None)
            if not obj.is_file() or not tex or _black_share(tex) > MAX_BLACK_SHARE:
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            for f in work.glob("textured*"):
                if f.suffix.lower() in (".obj", ".mtl", ".png", ".jpg", ".jpeg"):
                    shutil.copy2(f, out_dir / f.name)
            glb = out_dir / "model.glb"
            trimesh.load(str(obj), force="mesh").export(str(glb))
            return out_dir / obj.name, glb
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, ImportError):
            continue
    return None


def run_colmap_pipeline(
    image_dir: Path,
    out_dir: Path,
    sequential: bool = False,
    remove_bg: bool = False,
) -> tuple[Path, Path]:
    """
    End-to-end: images → COLMAP SfM+MVS → Poisson mesh → OBJ/GLB.
    Returns (obj_path, glb_path).
    """
    work_dir = out_dir / "_colmap_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        mask_dir = None
        if remove_bg:  # 물체에서만 특징점을 찾게 — 배경이 복잡하거나 회전대 위 촬영에 효과
            from app.services import bg_remove
            if bg_remove.available() and bg_remove.write_masks(image_dir, work_dir / "masks"):
                mask_dir = work_dir / "masks"
        fused_ply = run_colmap_sfm(image_dir, work_dir, sequential=sequential, mask_dir=mask_dir)
        n = _ply_vertex_count(fused_ply)
        if n < MIN_POINTS:
            raise RuntimeError(
                f"복원된 점이 {n}개뿐이라 형태를 만들 수 없습니다. 사진을 더 겹치게(옆 사진과 60% 이상) 찍거나, "
                "NVIDIA GPU 가 있으면 scripts/install-colmap.bat 으로 GPU판을 설치하세요(정밀 복원).")
        obj_abs, glb_abs = ply_to_mesh(fused_ply, out_dir)
        meshed = fused_ply.with_name("meshed-poisson.ply")
        if fused_ply.name == "fused.ply" and meshed.is_file():  # 정밀(GPU) 복원일 때만 — 사진 색 입히기
            textured = texture_mesh(fused_ply.parent, meshed, out_dir)
            if textured:
                obj_abs, glb_abs = textured
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
