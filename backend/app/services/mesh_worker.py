"""Background mesh generation: heightfield (CPU), TripoSR (GPU), or COLMAP (multi-image)."""
from __future__ import annotations

import asyncio
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

MIN_COLMAP_IMAGES = 5  # 사진측량은 겹치는 사진이 충분해야 함


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
        if (rec.detail or {}).get("remove_bg") and rec.type != JobType.multi_image:
            from app.services import bg_remove
            if bg_remove.available():  # 1장: 배경 지우고 그 사진으로 메시·PBR (배경은 높이 0)
                await job_store.set_status(job_id, JobStatus.running, "배경 지우는 중…")
                cut = await asyncio.to_thread(bg_remove.cutout, img_path, out_dir / "cutout.png")
                img_path = await asyncio.to_thread(bg_remove.flatten_on_black, cut, out_dir / "input_nobg.png")

        # 여러 각도 사진 → COLMAP 사진측량 (이 PC 에서만 실행, 외부 서버 전송 없음)
        from app.services.colmap_runner import colmap_available, colmap_has_cuda, run_colmap_pipeline

        use_colmap = backend == "colmap" or (rec.type == JobType.multi_image and len(paths) >= MIN_COLMAP_IMAGES
                                             and colmap_available())
        if use_colmap:
            if not colmap_available():
                raise RuntimeError("COLMAP 이 설치되지 않았습니다 — scripts/install-colmap.bat 을 실행하세요.")
            dense = colmap_has_cuda()
            await job_store.set_status(job_id, JobStatus.running,
                                       f"사진 {len(paths)}장으로 3D 복원 중 ({'정밀·GPU' if dense else '대략·CPU'}) — 수 분 걸립니다")
            img_dir = UPLOAD_ROOT / str(job_id)
            obj_abs, glb_abs = await asyncio.to_thread(run_colmap_pipeline, img_dir, out_dir,
                                                       remove_bg=bool((rec.detail or {}).get("remove_bg")))
            method = "colmap_dense_poisson" if dense else "colmap_sparse_poisson"
            note = ("COLMAP SfM + MVS (GPU) + Poisson — 사진측량 결과." if dense else
                    "CUDA 없는 COLMAP: 희소 점으로 만든 대략적인 형태입니다. NVIDIA GPU 가 있으면 install-colmap.bat 으로 GPU판 설치.")
            ok_msg = f"메시 완성 (COLMAP, 사진 {len(paths)}장)"
        elif rec.type == JobType.multi_image:
            note_multi = (f"사진 {len(paths)}장 — 여러 각도 복원은 {MIN_COLMAP_IMAGES}장 이상 필요" if colmap_available()
                          else "COLMAP 미설치 — scripts/install-colmap.bat 실행 후 여러 각도 복원 가능")
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

        if use_colmap:
            pass
        elif backend == "triposr":
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
            if rec.type == JobType.multi_image and not use_colmap:
                note = note_multi + " · 지금은 첫 사진으로 부조(높이맵) 메시를 만들었습니다."

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
