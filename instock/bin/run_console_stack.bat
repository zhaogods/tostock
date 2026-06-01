chcp 65001
@echo off
set "BIN_DIR=%~dp0"
set "SCHEDULER_DIR=%BIN_DIR%..\scheduler"
set "WEB_DIR=%BIN_DIR%..\web"

echo ------正在启动调度服务窗口，请不要关闭调度窗口------
start "InStock Scheduler" /D "%SCHEDULER_DIR%" cmd /k python scheduler_service.py

echo ------正在启动Web服务，请不要关闭本窗口------
echo 访问地址 : http://localhost:9988/
cd /d "%WEB_DIR%"
python web_service.py

echo ------Web服务已停止------
pause
exit
