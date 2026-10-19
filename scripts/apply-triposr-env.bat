@echo off
REM Auto-enable TripoSR for Pix2Poly when third_party\TripoSR is installed
set "ROOT=%~dp0.."
set "TR=%ROOT%third_party\TripoSR"
if exist "%TR%\run.py" if exist "%TR%\.venv\Scripts\python.exe" (
  set "PIX2POLY_MESH_BACKEND=triposr"
  set "PIX2POLY_TRIPOSR_REPO_PATH=%TR%"
  set "PIX2POLY_TRIPOSR_PYTHON=%TR%\.venv\Scripts\python.exe"
  REM TripoSR run.py falls back to CPU if CUDA is unavailable
  if "%PIX2POLY_TRIPOSR_DEVICE%"=="" set "PIX2POLY_TRIPOSR_DEVICE=cuda:0"
  echo [Pix2Poly] TripoSR env ON: %TR% device=%PIX2POLY_TRIPOSR_DEVICE%
) else (
  echo [Pix2Poly] TripoSR not ready — run scripts\install-triposr-windows.bat
)
