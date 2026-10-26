"""
CPU-based PBR map generation from a single albedo image.

Generates: albedo, normal, roughness, metallic, ao (ambient occlusion).
Uses only NumPy + Pillow (no OpenCV required) so it works in the base venv.
If opencv-python-headless is installed, higher-quality Gaussian blur is used.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_float(arr: np.ndarray) -> np.ndarray:
    """uint8 HxWxC → float32 in [0, 1]."""
    return arr.astype(np.float32) / 255.0


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    """float32 [0,1] → uint8, clamp."""
    return np.clip(arr * 255.0, 0, 255).astype(np.uint8)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    """rgb float32 HxWx3 → gray float32 HxW in [0,1]."""
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def _sobel(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Simple 3x3 Sobel on float32 HxW. Returns (gx, gy)."""
    from numpy.lib.stride_tricks import as_strided  # noqa: F401 – not used, but kept for clarity

    # Use PIL or manual convolution
    try:
        import cv2  # type: ignore

        g8 = _to_uint8(gray[..., np.newaxis])[:, :, 0]
        gx = cv2.Sobel(g8, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g8, cv2.CV_32F, 0, 1, ksize=3)
        # Normalise to [-1, 1]
        m = max(np.abs(gx).max(), np.abs(gy).max(), 1e-6)
        return gx / m, gy / m
    except ImportError:
        pass

    # Pure NumPy fallback Sobel
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
    h, w = gray.shape
    pad = np.pad(gray, 1, mode="reflect")
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    for di in range(3):
        for dj in range(3):
            gx += kx[di, dj] * pad[di : di + h, dj : dj + w]
            gy += ky[di, dj] * pad[di : di + h, dj : dj + w]
    m = max(np.abs(gx).max(), np.abs(gy).max(), 1e-6)  # X·Y 같은 값으로 나눠야 기울기 비율이 유지됨
    return gx / m, gy / m


def _box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    """Fast separable box blur on float32 HxW."""
    try:
        import cv2  # type: ignore

        k = 2 * radius + 1
        return cv2.blur(arr, (k, k))
    except ImportError:
        pass
    # Pure NumPy: cumsum-based box filter
    # 누적합 앞에 0 을 붙여야 창 합계 = cs[i+k] - cs[i] 가 정확히 h(w) 개 나온다
    # (이전 구현은 길이가 1 어긋나 OpenCV 없는 기본 설치에서 항상 ValueError)
    k = 2 * radius + 1
    pad = np.pad(arr, radius, mode="reflect")
    cs = np.concatenate([np.zeros((1, pad.shape[1])), np.cumsum(pad, axis=0)], axis=0)
    vert = cs[k:] - cs[:-k]
    cs2 = np.concatenate([np.zeros((vert.shape[0], 1)), np.cumsum(vert, axis=1)], axis=1)
    out = cs2[:, k:] - cs2[:, :-k]
    return out / (k * k)


# ---------------------------------------------------------------------------
# Map generators
# ---------------------------------------------------------------------------

def _generate_normal_map(gray: np.ndarray, strength: float = 2.0) -> np.ndarray:
    """
    gray float32 HxW → normal map uint8 HxWx3.
    Convention: OpenGL / glTF — R=+X, G=+Y(up), B=+Z. (Unreal/DirectX: invert G)  Tangent-space (purple-ish base).
    """
    gx, gy = _sobel(gray)
    gx = gx * strength
    gy = gy * strength
    gz = np.ones_like(gx)
    length = np.sqrt(gx ** 2 + gy ** 2 + gz ** 2) + 1e-8
    nx = -gx / length
    ny = gy / length  # OpenGL(+Y 위) 규약 — glTF·Blender·Unity 기본. gy 는 이미지 아래 방향 기울기라 부호가 반대 (Unreal 은 G 반전)
    nz = gz / length
    # Map [-1,1] → [0,255]
    normal = np.stack(
        [(nx + 1.0) * 0.5, (ny + 1.0) * 0.5, (nz + 1.0) * 0.5], axis=-1
    )
    return _to_uint8(normal)


def _generate_roughness_map(gray: np.ndarray) -> np.ndarray:
    """
    Roughness ≈ normalised multi-scale local contrast.
    High contrast regions → rougher.
    """
    blurred = _box_blur(gray, 4)
    diff = np.abs(gray - blurred)
    # Normalise per-image
    d_max = diff.max()
    if d_max < 1e-8:
        rough = np.full_like(gray, 0.5)
    else:
        rough = diff / d_max
    # Remap: push midpoint to ~0.5 for typical images
    rough = np.clip(rough * 2.5, 0.0, 1.0)
    return _to_uint8(rough)


def _generate_metallic_map(rgb_float: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """
    Simple heuristic: highly saturated dark pixels → less metallic.
    Very bright, low-saturation areas → more metallic.
    Default is nearly all dielectric (0.0); override via env if needed.
    """
    # Saturation: S = (max - min) / max
    mx = rgb_float.max(axis=-1)
    mn = rgb_float.min(axis=-1)
    sat = np.where(mx > 1e-6, (mx - mn) / (mx + 1e-8), 0.0)
    # Metal likelihood: bright + low saturation
    metal = gray * (1.0 - sat)
    metal = np.clip(metal * 1.5 - 0.6, 0.0, 1.0)  # push most to 0
    return _to_uint8(metal)


def _generate_ao_map(gray: np.ndarray) -> np.ndarray:
    """
    Approximate AO: darker than neighbourhood → more occluded.
    """
    scales = [4, 8, 16]
    ao = np.zeros_like(gray)
    for r in scales:
        blurred = _box_blur(gray, r)
        # Where pixel is darker than surroundings → cavity
        diff = blurred - gray  # positive in dark pits
        ao += np.clip(diff, 0.0, None)
    ao /= len(scales)
    a_max = ao.max()
    if a_max > 1e-8:
        ao = ao / a_max
    # Invert so bright = unoccluded (standard AO convention)
    ao = 1.0 - np.clip(ao * 2.0, 0.0, 1.0)
    return _to_uint8(ao)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pbr_maps(
    image_path: Path,
    out_dir: Path,
    normal_strength: float = 2.0,
) -> dict[str, Path]:
    """
    Read an image from disk and write 5 PBR PNG maps into out_dir/pbr/.

    Returns dict with keys: albedo, normal, roughness, metallic, ao
    Values are absolute Paths to the written PNGs.
    """
    out_dir = out_dir / "pbr"
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    # Work at a reasonable PBR texture resolution
    target = 512
    if img.width < target and img.height < target:
        target = max(img.width, img.height)
    img = img.resize((target, target), Image.Resampling.LANCZOS)

    rgb_arr = np.asarray(img, dtype=np.uint8)
    rgb_f = _as_float(rgb_arr)
    gray = _luminance(rgb_f)

    paths: dict[str, Path] = {}

    # Albedo — the input image itself (resized to target)
    albedo_path = out_dir / "albedo.png"
    img.save(str(albedo_path))
    paths["albedo"] = albedo_path

    # Normal
    normal_path = out_dir / "normal.png"
    normal_arr = _generate_normal_map(gray, strength=normal_strength)
    Image.fromarray(normal_arr, "RGB").save(str(normal_path))
    paths["normal"] = normal_path

    # Roughness (grayscale saved as L)
    roughness_path = out_dir / "roughness.png"
    rough_arr = _generate_roughness_map(gray)
    Image.fromarray(rough_arr, "L").save(str(roughness_path))
    paths["roughness"] = roughness_path

    # Metallic
    metallic_path = out_dir / "metallic.png"
    metal_arr = _generate_metallic_map(rgb_f, gray)
    Image.fromarray(metal_arr, "L").save(str(metallic_path))
    paths["metallic"] = metallic_path

    # AO
    ao_path = out_dir / "ao.png"
    ao_arr = _generate_ao_map(gray)
    Image.fromarray(ao_arr, "L").save(str(ao_path))
    paths["ao"] = ao_path

    return paths
