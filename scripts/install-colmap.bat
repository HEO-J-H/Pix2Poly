@echo off
rem Pix2Poly - COLMAP(사진측량, BSD 라이선스) 공식 릴리스를 내려받아 colmap\ 에 설치
rem NVIDIA GPU 가 있으면 CUDA판(정밀 복원), 없으면 일반판(대략적인 형태)을 받습니다.
rem 출처: https://github.com/colmap/colmap/releases (공식 저장소만 사용)
setlocal
cd /d "%~dp0.."
set VER=4.2.1
set KIND=nocuda
where nvidia-smi >nul 2>&1 && set KIND=cuda
set URL=https://github.com/colmap/colmap/releases/download/%VER%/colmap-x64-windows-%KIND%.zip
echo.
echo COLMAP %VER% (%KIND%) 내려받는 중... (CUDA판 약 400MB, 일반판 약 120MB)
echo   %URL%
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile 'colmap-download.zip'" || goto :fail
if exist colmap rmdir /s /q colmap
powershell -NoProfile -Command "Expand-Archive -Force 'colmap-download.zip' 'colmap-tmp'" || goto :fail
rem 압축 안 폴더 이름이 바뀌어도 COLMAP.bat 이 있는 폴더를 colmap\ 으로
for /f "delims=" %%D in ('dir /s /b colmap-tmp\COLMAP.bat') do set SRC=%%~dpD
move "%SRC:~0,-1%" colmap >nul
rmdir /s /q colmap-tmp
del colmap-download.zip
call colmap\COLMAP.bat -h | findstr /c:"COLMAP"
echo.
echo 설치 완료. run.bat 으로 Pix2Poly 를 실행하고 '여러 장' 탭에 같은 물체를 5장 이상 넣으세요.
pause
exit /b 0
:fail
echo 내려받기 또는 압축 풀기에 실패했습니다. 인터넷 연결을 확인하고 다시 실행하세요.
pause
exit /b 1
