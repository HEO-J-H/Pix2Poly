@echo off
rem Pix2Poly - install official COLMAP (BSD) from github.com/colmap/colmap/releases into colmap\r
rem NVIDIA GPU: CUDA build (dense reconstruction), otherwise no-CUDA build.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-colmap.ps1"
pause
