"""배경 제거 — 물체만 남겨 3D 품질을 높임 (rembg, MIT · 이 PC 에서만 실행, 사진을 밖으로 보내지 않음).

- 1장: 배경을 투명(→ 높이 0)으로 만든 사진을 메시·PBR 에 사용
- 여러 장(COLMAP): 사진마다 마스크(흰=물체, 검=배경)를 만들어 특징점을 물체에서만 찾게 함
모델(isnet-general-use, 약 170MB)은 처음 쓸 때 rembg 공식 GitHub 릴리스에서 한 번 내려받음.
"""
from __future__ import annotations

from pathlib import Path

MODEL = "isnet-general-use"
_session = None


def available() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def _get_session():
    global _session
    if _session is None:
        from rembg import new_session
        _session = new_session(MODEL)
    return _session


def cutout(src: Path, dst: Path) -> Path:
    """배경을 지운 RGBA PNG 를 dst 에 저장."""
    from PIL import Image
    from rembg import remove
    out = remove(Image.open(src).convert("RGB"), session=_get_session())
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst


def flatten_on_black(rgba: Path, dst: Path) -> Path:
    """투명 배경을 검정으로 — 높이맵에서 배경이 바닥(높이 0)이 되게."""
    from PIL import Image
    im = Image.open(rgba).convert("RGBA")
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    bg.alpha_composite(im)
    bg.convert("RGB").save(dst)
    return dst


def write_masks(image_dir: Path, mask_dir: Path) -> int:
    """COLMAP 용 마스크: <사진이름>.png (흰=사용, 검=무시). 만든 개수 반환."""
    from PIL import Image
    from rembg import remove
    mask_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(image_dir.iterdir()):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            continue
        m = remove(Image.open(f).convert("RGB"), session=_get_session(), only_mask=True)
        m.point(lambda v: 255 if v > 127 else 0).convert("L").save(mask_dir / (f.name + ".png"))
        n += 1
    return n
