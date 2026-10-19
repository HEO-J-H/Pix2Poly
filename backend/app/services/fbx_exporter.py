"""
FBX exporter for Pix2Poly.

Strategy A (preferred): Blender headless CLI
  blender --background --python <script> -- <input.glb> <output.fbx>

Strategy B (fallback): trimesh → OBJ is already exported; advise the user to
  open it in Blender/Maya/3ds Max to re-export as FBX.

The function always tries Strategy A first (if `blender` or BLENDER_PATH is
resolvable), then falls back gracefully.

Environment variables:
  PIX2POLY_BLENDER_PATH  – absolute path to the Blender executable.
                           Defaults to "blender" (must be on PATH).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = """\
import sys, bpy

argv = sys.argv
sep = argv.index("--") if "--" in argv else len(argv)
args = argv[sep + 1:]
src, dst = args[0], args[1]

bpy.ops.wm.read_homefile(use_empty=True)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

ext = src.rsplit(".", 1)[-1].lower()
if ext == "glb" or ext == "gltf":
    bpy.ops.import_scene.gltf(filepath=src)
elif ext == "obj":
    try:
        bpy.ops.wm.obj_import(filepath=src)
    except AttributeError:
        bpy.ops.import_scene.obj(filepath=src)
else:
    raise ValueError(f"Unsupported input format: {ext}")

bpy.ops.export_scene.fbx(
    filepath=dst,
    use_selection=False,
    embed_textures=False,
    path_mode="COPY",
    axis_forward="-Z",
    axis_up="Y",
)
print("FBX exported to", dst)
"""


def _blender_executable() -> str | None:
    """Return path to Blender binary or None if not found."""
    env_path = os.environ.get("PIX2POLY_BLENDER_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    found = shutil.which("blender")
    return found  # None if not on PATH


def export_to_fbx(src_path: Path, out_dir: Path) -> Path | None:
    """
    Convert src_path (GLB or OBJ) to FBX using Blender headless.

    Returns the absolute Path to the .fbx on success, or None if Blender is
    unavailable.  Never raises — logs warnings and returns None on failure.
    """
    blender = _blender_executable()
    if blender is None:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    fbx_path = out_dir / "model.fbx"

    # Write the inline Blender Python script to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(BLENDER_SCRIPT)
        script_file = tf.name

    try:
        result = subprocess.run(
            [
                blender,
                "--background",
                "--python", script_file,
                "--",
                str(src_path),
                str(fbx_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace")[-2000:]
            print(f"[fbx_exporter] Blender exited {result.returncode}: {err}", file=sys.stderr)
            return None
        if not fbx_path.exists():
            print("[fbx_exporter] FBX not created despite zero exit code.", file=sys.stderr)
            return None
        return fbx_path
    except FileNotFoundError:
        print("[fbx_exporter] Blender binary not found.", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("[fbx_exporter] Blender timed out.", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[fbx_exporter] Unexpected error: {exc}", file=sys.stderr)
        return None
    finally:
        try:
            Path(script_file).unlink(missing_ok=True)
        except Exception:
            pass


def fbx_available() -> bool:
    """True if Blender is accessible (FBX export will work)."""
    return _blender_executable() is not None
