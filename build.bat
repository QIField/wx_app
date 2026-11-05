@echo off
echo ================================================
echo  Building frontend (npm run build) ...
echo ================================================
cd /d %~dp0frontend
call npm run build
if errorlevel 1 (
    echo.
    echo [FAILED] Build error! Do NOT upload to server.
    pause
    exit /b 1
)
echo.
echo [OK] Build done. Upload frontend\dist to server.
pause
