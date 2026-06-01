chcp 65001
@echo off
cd %~dp0
cd ..
cd scheduler
python scheduler_service.py
echo ------调度服务已启动，请不要关闭------
pause
exit
