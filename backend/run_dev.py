"""
Run FastAPI with uvicorn --reload and watch multiple file types (py, html, css, js, json).
Usage (from backend/): python run_dev.py
Environment: PORT (default 8000)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    backend = Path(__file__).resolve().parent
    os.chdir(backend)
    port = os.environ.get("PORT", "8000")

    # Watch only source dirs (avoids .venv/uploads and Windows glob issues with ** in --reload-exclude)
    reload_dirs = [
        backend / "app",
        backend / "static",
    ]
    include_patterns = [
        "*.py",
        "*.html",
        "*.htm",
        "*.css",
        "*.js",
        "*.json",
    ]

    args: list[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    for d in reload_dirs:
        if d.is_dir():
            args.extend(["--reload-dir", str(d)])
    for pat in include_patterns:
        args.extend(["--reload-include", pat])

    raise SystemExit(subprocess.call(args))


if __name__ == "__main__":
    main()
