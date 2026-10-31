import subprocess

import pytest

from backend.app.services import trellis_cpp as tc


def _setup(tmp_path, monkeypatch):
    exe, model, img = tmp_path / "trellis.exe", tmp_path / "m.gguf", tmp_path / "a.png"
    for f in (exe, model, img):
        f.write_bytes(b"x")
    monkeypatch.setenv("TRELLIS_CPP_BIN", str(exe))
    monkeypatch.setenv("TRELLIS_CPP_MODEL", str(model))
    monkeypatch.delenv("TRELLIS_CPP_ARGS", raising=False)
    return img


def test_not_installed(monkeypatch):
    monkeypatch.delenv("TRELLIS_CPP_BIN", raising=False)
    ok, why = tc.available()
    assert not ok and "미설치" in why
    with pytest.raises(RuntimeError):
        tc.run("a.png", "b.glb")


def test_runs_without_shell_and_checks_output(tmp_path, monkeypatch):
    img = _setup(tmp_path, monkeypatch)
    out = tmp_path / "o.glb"
    seen = {}

    def fake(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        out.write_bytes(b"glb")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(tc.subprocess, "run", fake)
    assert tc.run(img, out) == out
    assert seen["shell"] is False and isinstance(seen["cmd"], list) and str(img) in seen["cmd"]


def test_timeout_and_missing_output(tmp_path, monkeypatch):
    img = _setup(tmp_path, monkeypatch)

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])
    monkeypatch.setattr(tc.subprocess, "run", slow)
    with pytest.raises(RuntimeError, match="초 안에"):
        tc.run(img, tmp_path / "o.glb", timeout=5)
    monkeypatch.setattr(tc.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    with pytest.raises(RuntimeError, match="GLB"):
        tc.run(img, tmp_path / "none.glb")
