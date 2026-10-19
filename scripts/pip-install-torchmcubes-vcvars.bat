@echo off
REM Run from install-triposr-windows.bat with TR set to TripoSR root (absolute path).
if "%TR%"=="" (
  echo TR is not set.
  exit /b 1
)
REM Short path avoids cmd.exe parsing bugs with parentheses in "Program Files (x86)"
set "VCVARS=C:\PROGRA~2\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo vcvars64.bat not found: %VCVARS%
  exit /b 1
)
call "%VCVARS%"
REM CMake needs nvcc on PATH; vcvars does not add CUDA Toolkit (installed separately).
REM Prefer CUDA 12.4 for PyTorch cu124 wheels; 13.x can break CMake nvToolsExt with torch 2.6
if "%CUDA_PATH%"=="" (
  if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\nvcc.exe" set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4"
)
if "%CUDA_PATH%"=="" (
  if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
)
if "%CUDA_PATH%"=="" (
  if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin\nvcc.exe" set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2"
)
if not "%CUDA_PATH%"=="" (
  set "PATH=%CUDA_PATH%\bin;%CUDA_PATH%\libnvvp;%PATH%"
  set "CUDA_HOME=%CUDA_PATH%"
  set "CudaToolkitDir=%CUDA_PATH%"
  REM Avoid VS MSBuild CUDA 13.x targets + nvcc 12.x mismatch; Ninja skips MSBuild CUDA integration
  set "CMAKE_ARGS=-GNinja"
  echo Using CUDA_PATH=%CUDA_PATH%
) else (
  echo WARNING: CUDA Toolkit not found under Program Files. torchmcubes may fail for CUDA PyTorch.
)
cd /d "%TR%"
set "PATH=%TR%\.venv\Scripts;%PATH%"
REM PyTorch find_package(Torch) only finds nvtx3 under third_party/NVTX in the consumer project; add CUDA toolkit include
"%TR%\.venv\Scripts\python.exe" "%~dp0patch_torch_cuda_nvtx.py" "%TR%"
REM Build isolation drops CUDA_* env vars; CMAKE_ARGS=-GNinja avoids VS CUDA 13 targets vs nvcc 12 mismatch
"%TR%\.venv\Scripts\pip.exe" install --no-build-isolation git+https://github.com/tatsy/torchmcubes.git
exit /b %ERRORLEVEL%
