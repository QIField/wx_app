@echo off
rem 后端守护：进程退出后 3 秒自动拉起，崩溃原因追加到 logs\backend.log
rem 用法：双击运行，或命令行 start restart-dev.bat；停止服务直接关掉本窗口
cd /d %~dp0
title wx_app 后端守护（关闭本窗口=停止守护）
chcp 65001 >nul
if not exist logs mkdir logs
set PYTHONUTF8=1

:loop
.venv\Scripts\python.exe -u -m backend.app >> logs\backend.log 2>&1
echo [%date% %time%] backend exited (code %errorlevel%), restarting in 3s... >> logs\backend.log
timeout /t 3 /nobreak >nul
goto loop
