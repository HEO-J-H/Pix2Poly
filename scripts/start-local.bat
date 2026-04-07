@echo off
setlocal
cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"
pip install -r requirements.txt -q

if "%PORT%"=="" set PORT=8000

echo.
echo Pix2Poly (local)
echo   UI:  http://127.0.0.1:%PORT%/ui/
echo   API: http://127.0.0.1:%PORT%/docs
echo.
echo Opening browser in 2 seconds...
REM Async: wait for uvicorn to bind, then open default browser (does not block server)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:%PORT%/ui/"

python run_dev.py

pause
