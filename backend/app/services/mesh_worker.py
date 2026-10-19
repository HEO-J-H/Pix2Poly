"""Background mesh generation: heightfield (CPU), TripoSR (GPU), or COLMAP (multi-image)."""
from __future__ import annotations

import traceback
from uuid import UUID

from app.schemas import JobStatus, JobType
from app.services.fbx_exporter import export_to_fbx
from app.services.jobs import job_store
from app.services.mesh_from_image import mesh_from_image_file
from app.services.pbr_generator import generate_pbr_maps
from app.services.storage import OUTPUT_ROOT, UPLOAD_ROOT, ensure_output_dir, resolve_under_uploads
from app.settings_mesh import (
    instantmesh_repo_path,
    mesh_backend,
    triposr_device,
    triposr_python,
    triposr_repo_path,
)


async def build_mesh_for_image_job(job_id: UUID) -> None:
    await job_store.set_status(job_id, JobStatus.running, "Generating mesh…")
    try:
        rec = await job_store.get(job_id)
        if not rec:
            return
        # Accept single_image, multi_image, and url types (url-images endpoint)
        if rec.type not in (JobType.single_image, JobType.multi_image, JobType.url):
            return
        paths = (rec.detail or {}).get("upload_paths") or []
        if not paths:
            raise ValueError("No upload_paths on job")
        first_rel = paths[0]
        img_path = resolve_under_uploads(first_rel)
        if not img_path.is_file():
            raise FileNotFoundError(str(img_path))

        out_dir = ensure_output_dir(job_id)
        backend = mesh_backend()

        # COLMAP multi-image path: use when >= 3 images + colmap backend
        if backend == "colmap" or (len(paths) >= 3 and backend in ("colmap",)):
            from app.services.colmap_runner import run_colmap_pipeline, colmap_available

            if not colmap_available():
                raise RuntimeError(
                    "COLMAP binary not found. Install COLMAP and ensure it is on PATH, "
                    "or set PIX2POLY_COLMAP_PATH. Falling back is not automatic — "
                    "set PIX2POLY_MESH_BACKEND=heightfield for CPU fallback."
                )
            # Build an image directory with all uploaded images
            img_dir = UPLOAD_ROOT / str(job_id)
            obj_abs, glb_abs = run_colmap_pipeline(img_dir, out_dir)
            method = "colmap_sfm_poisson"
            note = "COLMAP SfM + MVS + Poisson reconstruction from multi-image set."
            ok_msg = "Mesh ready (COLMAP SfM)."

        elif backend == "instantmesh":
            await job_store.set_status(
                job_id,
                JobStatus.failed,
                "InstantMesh is not auto-wired in this repo (CLI/output layout varies). "
                "Use PIX2POLY_MESH_BACKEND=triposr or extend mesh_worker — see docs/gpu-worker.md",
                detail_update={
                    "mesh_backend": "instantmesh",
                    "instantmesh_repo": str(instantmesh_repo_path() or ""),
                    "hint": "docs/gpu-worker.md#2-instantmesh",
                },
            )
            return

        if backend == "triposr":
            from app.services.triposr_runner import run_triposr_to_output_dir

            repo = triposr_repo_path()
            if not repo:
                raise ValueError(
                    "PIX2POLY_MESH_BACKEND=triposr requires PIX2POLY_TRIPOSR_REPO_PATH "
                    "(absolute path to cloned TripoSR). See docs/gpu-worker.md"
                )
            py = triposr_python()
            obj_abs, glb_abs = run_triposr_to_output_dir(
                img_path,
                out_dir,
                repo,
                py,
                device=triposr_device(),
            )
            method = "triposr"
            note = "TripoSR feed-forward mesh. FBX: import OBJ/GLB in Blender and export."
            ok_msg = "Mesh ready (TripoSR)."
        else:
            obj_abs, glb_abs = mesh_from_image_file(img_path, out_dir, grid=200, height_scale=0.45)
            method = "heightfield_luminance"
            note = (
                "Baseline relief mesh (CPU). Set PIX2POLY_MESH_BACKEND=triposr for TripoSR. "
                "FBX: import OBJ in Blender and export."
            )
            ok_msg = "Mesh ready (heightfield from luminance)."

        backend_root = OUTPUT_ROOT.parent
        obj_rel = str(obj_abs.relative_to(backend_root)).replace("\\", "/")
        glb_rel = str(glb_abs.relative_to(backend_root)).replace("\\", "/")

        # Generate PBR maps from the source image
        pbr_detail: dict = {}
        try:
            pbr_paths = generate_pbr_maps(img_path, out_dir)
            pbr_detail = {
                k: str(v.relative_to(backend_root)).replace("\\", "/")
                for k, v in pbr_paths.items()
            }
        except Exception as _pbr_err:
            pbr_detail = {"error": str(_pbr_err)}

        # FBX export (requires Blender on PATH or PIX2POLY_BLENDER_PATH)
        fbx_rel: str | None = None
        try:
            fbx_abs = export_to_fbx(glb_abs, out_dir)
            if fbx_abs and fbx_abs.exists():
                fbx_rel = str(fbx_abs.relative_to(backend_root)).replace("\\", "/")
        except Exception as _fbx_err:
            pass

        output_paths = [obj_rel, glb_rel]
        if fbx_rel:
            output_paths.append(fbx_rel)
        formats = ["obj", "glb"] + (["fbx"] if fbx_rel else [])

        # Collect all output paths (mesh + PBR textures) for download links
        all_output_paths = output_paths + list(
            pbr_detail.values() if "error" not in pbr_detail else []
        )

        await job_store.set_status(
            job_id,
            JobStatus.succeeded,
            ok_msg,
            detail_update={
                "output_paths": output_paths,
                "pbr_paths": pbr_detail,
                "all_artifact_paths": all_output_paths,
                "formats": formats,
                "mesh_method": method,
                "mesh_backend": backend,
                "note": note,
            },
        )
    except Exception as e:
        tb = traceback.format_exc()
        await job_store.set_status(
            job_id,
            JobStatus.failed,
            str(e) or "mesh generation failed",
            detail_update={"error_trace": tb[-4000:]},
        )
