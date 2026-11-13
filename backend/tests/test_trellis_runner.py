import json
import subprocess

import pytest

from backend.app.services import trellis_runner as tr


def _setup(tmp_path, monkeypatch, n=1):
    repo = tmp_path / "TRELLIS"
    (repo / "trellis").mkdir(parents=True)
    imgs = []
    for i in range(n):
        p = tmp_path / f"v{i}.png"
        p.write_bytes(b"x")
        imgs.append(p)
    monkeypatch.setenv("TRELLIS_REPO", str(repo))
    monkeypatch.setenv("TRELLIS_PYTHON", "py-test")
    monkeypatch.delenv("TRELLIS_MODEL", raising=False)
    return repo, imgs


def test_not_installed(monkeypatch):
    monkeypatch.delenv("TRELLIS_REPO", raising=False)
    ok, why = tr.available()
    assert not ok and "미설치" in why
    with pytest.raises(RuntimeError, match="미설치"):
        tr.run(["a.png"], "b.glb")


def test_multi_image_args_and_no_shell(tmp_path, monkeypatch):
    repo, imgs = _setup(tmp_path, monkeypatch, n=3)
    out = tmp_path / "out" / "model.glb"
    seen = {}

    def fake(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        out.write_bytes(b"glb")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(tr.subprocess, "run", fake)
    assert tr.run(imgs, out) == out
    assert seen["shell"] is False and seen["cmd"][0] == "py-test" and seen["cwd"] == str(repo)
    args = json.loads(seen["cmd"][2])
    assert len(args["images"]) == 3 and args["model"] == tr.DEFAULT_MODEL
    assert "run_multi_image" in tr.DRIVER and "to_glb" in tr.DRIVER


def test_failures_are_clear(tmp_path, monkeypatch):
    _repo, imgs = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(tr.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("x", 5)))
    with pytest.raises(RuntimeError, match="초 안에 끝나지"):
        tr.run(imgs, tmp_path / "o.glb", timeout=5)
    monkeypatch.setattr(tr.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    with pytest.raises(RuntimeError, match="GLB 를 만들지 못했습니다"):
        tr.run(imgs, tmp_path / "o2.glb")
    with pytest.raises(RuntimeError, match="찾지 못했습니다"):
        tr.run([tmp_path / "none.png"], tmp_path / "o3.glb")
