"""
FlexPart runner – a lightweight placeholder implementation.

This module provides a minimal interface compatible with the existing
job orchestration.  The real FlexPart engine is optional; when it is
unavailable we fall back to a dummy implementation that copies the
input image and writes a minimal OBJ file so downstream code can
continue without errors.
"""

from pathlib import Path
import shutil


def run_flexpart_to_output_dir(
    image_path: Path,
    output_dir: Path,
    *,
    device: str = "cpu",
) -> dict:
    """
    Run FlexPart (or a stub) and store results in ``output_dir``.

    Parameters
    ----------
    image_path: Path
        Path to the source image.
    output_dir: Path
        Directory where FlexPart should write its artefacts.
    device: str, optional
        Device selector (e.g., ``"cpu"`` or ``"cuda"``).  Currently unused
        by the stub implementation.

    Returns
    -------
    dict
        Mapping of artefact names to file paths.  At minimum contains
        ``\"mesh\"`` pointing to an OBJ file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy the source image for reference – downstream pipelines may
    # expect the original image to be present alongside the mesh.
    input_copy = output_dir / image_path.name
    shutil.copy2(image_path, input_copy)

    # Create a minimal OBJ file so that callers that expect a mesh can
    # proceed.  The content is a single vertex and a single face.
    mesh_path = output_dir / "mesh.obj"
    mesh_path.write_text(
        "v 0.0 0.0 0.0\n"
        "v 1.0 0.0 0.0\n"
        "v 0.0 1.0 0.0\n"
        "f 1 2 3\n",
        encoding="utf-8",
    )

    return {"mesh": mesh_path}