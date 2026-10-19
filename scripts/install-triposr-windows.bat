@echo off
REM Clone (if needed), venv, PyTorch, TripoSR deps, then torchmcubes (VS C++ Build Tools required).
REM If CUDA Toolkit is not installed, torchmcubes is built against CPU PyTorch (slower; GPU inference needs CUDA Toolkit + cu124 PyTorch).
cd /d "%~dp0.."
set "TR=%CD%\third_party\TripoSR"

if not exist "%TR%\run.py" (
  echo Cloning TripoSR...
  mkdir third_party 2>nul
  git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git "%TR%"
)
cd /d "%TR%"
if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
echo Installing PyTorch ^(CUDA 12.4 wheel; falls back to CPU if needed^)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 -q
if errorlevel 1 pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu -q
echo Installing TripoSR deps ^(without torchmcubes^)...
pip install -r "%~dp0triposr-requirements-no-mcubes.txt" -q
echo.
echo === torchmcubes ^(C++ extension; MSVC via vcvars64^) ===
if not exist "C:\PROGRA~2\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
  echo Install "Visual Studio Build Tools 2022" with workload "Desktop development with C++".
  pause
  exit /b 1
)
echo.
echo Attempting torchmcubes ^(CUDA PyTorch needs CUDA Toolkit on PATH^)...
call "%~dp0pip-install-torchmcubes-vcvars.bat"
if errorlevel 1 (
  echo.
  echo CUDA build failed ^(typical: CUDA Toolkit not installed^). Retrying with CPU PyTorch + torchmcubes...
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --force-reinstall -q
  pip install "numpy>=1.0,<2" "Pillow>=8.0,<11" "markupsafe>=2.0,<3" -q
  call "%~dp0pip-install-torchmcubes-vcvars.bat"
  if errorlevel 1 (
    echo.
    echo [FAILED] torchmcubes. Pix2Poly can still use heightfield backend.
    pause
    exit /b 1
  )
)
echo.
echo Smoke test ^(temporary PNG, CPU^)...
set "SMOKEIN=%TEMP%\triposr_smoke_in.png"
python -c "from PIL import Image; Image.new('RGB',(256,256),(200,200,200)).save(r'%SMOKEIN%')"
python run.py "%SMOKEIN%" --output-dir "%TEMP%\triposr_smoke" --device cpu --chunk-size 512
if errorlevel 1 (
  echo Smoke test failed.
) else (
  echo TripoSR smoke OK.
)
echo.
echo Done. run.bat calls scripts\apply-triposr-env.bat so TripoSR is used when this venv is ready.
echo For NVIDIA GPU: install CUDA Toolkit 12.x, then run scripts\setup-triposr-gpu-windows.bat
pause
