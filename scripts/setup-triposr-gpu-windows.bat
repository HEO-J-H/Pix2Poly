@echo off
REM Upgrade TripoSR venv to PyTorch CUDA 12.4 wheels and rebuild torchmcubes against CUDA.
REM Requires: NVIDIA GPU driver, Visual Studio 2022 Build Tools (C++), CUDA Toolkit 12.x (nvcc on PATH for torchmcubes).
REM See docs/gpu-worker.md#windows-gpu-triposr
cd /d "%~dp0.."
set "TR=%CD%\third_party\TripoSR"
if not exist "%TR%\run.py" (
  echo Clone TripoSR first: run scripts\install-triposr-windows.bat
  pause
  exit /b 1
)
if not exist "%TR%\.venv\Scripts\python.exe" (
  echo Missing TripoSR venv. Run scripts\install-triposr-windows.bat
  pause
  exit /b 1
)
echo.
echo === TripoSR GPU setup ===
echo 1^) PyTorch cu124 wheels
echo 2^) CMake 3.27 + Ninja ^(torchmcubes build^)
echo 3^) Patch PyTorch cuda.cmake for nvtx3 ^(see scripts\patch_torch_cuda_nvtx.py^)
echo 4^) Rebuild torchmcubes ^(MSVC + CUDA 12.4 Toolkit^)
echo.
cd /d "%TR%"
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
echo Build helpers for torchmcubes...
pip install "cmake==3.27.7" scikit-build-core ninja pybind11 -q
echo Installing PyTorch CUDA 12.4 ^(replacing CPU wheels if present^)...
pip uninstall -y torch torchvision torchaudio 2>nul
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
pip install "numpy>=1.0,<2" "Pillow>=8.0,<11" "markupsafe>=2.0,<3" -q
echo.
echo Rebuilding torchmcubes ^(uninstall old wheel first^)...
pip uninstall -y torchmcubes 2>nul
call "%~dp0pip-install-torchmcubes-vcvars.bat"
if errorlevel 1 (
  echo.
  echo torchmcubes failed. Install CUDA Toolkit 12.x, ensure nvcc works, then run this script again.
  pause
  exit /b 1
)
echo.
echo === Verify ===
python -c "import torch, torchmcubes; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
echo.
echo Pix2Poly: run.bat sets PIX2POLY_TRIPOSR_DEVICE=cuda:0 via scripts\apply-triposr-env.bat
echo To force CPU: set PIX2POLY_TRIPOSR_DEVICE=cpu
pause
