@echo off
echo ============================================
echo  Pix2Poly 외부 도구 설치 확인
echo ============================================
echo.

echo [FFmpeg]
set FFMPEG=C:\Users\hjh10\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe
if exist "%FFMPEG%" (
    "%FFMPEG%" -version 2>&1 | findstr "ffmpeg version"
) else (
    echo NOT FOUND: %FFMPEG%
)
echo.

echo [COLMAP]
set COLMAP=C:\Pix2Poly\colmap\bin\colmap.exe
if exist "%COLMAP%" (
    "%COLMAP%" -h 2>&1 | findstr /i "colmap\|usage"
    echo COLMAP: OK at %COLMAP%
) else (
    echo NOT FOUND: %COLMAP%
)
echo.

echo [Blender]
set BLENDER=C:\Program Files\Blender Foundation\Blender 5.1\blender.exe
if exist "%BLENDER%" (
    echo BLENDER: OK at %BLENDER%
) else (
    echo NOT FOUND at 5.1, checking 4.3...
    set BLENDER=C:\Program Files\Blender Foundation\Blender 4.3\blender.exe
    if exist "%BLENDER%" (
        echo BLENDER: OK at %BLENDER%
    ) else (
        echo BLENDER: NOT FOUND
    )
)
echo.
echo ============================================
