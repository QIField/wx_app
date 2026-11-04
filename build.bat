@echo off
chcp 65001 >nul
echo 正在编译前端...
cd /d %~dp0frontend
call npm run build
if %errorlevel% neq 0 (
    echo.
    echo [失败] 前端编译出错，请检查上方错误信息，不要上传服务器！
    pause
    exit /b 1
)
echo.
echo [成功] 前端编译完成，请上传 frontend\dist 目录到服务器
pause
