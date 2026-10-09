@echo off
cd /d "%~dp0"
:: 仅关闭本导航站后端（按命令行特征匹配 server.py），不再误杀其他 Python 程序
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python%%' and CommandLine like '%%server.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 2 127.0.0.1 >nul
start "" /min pythonw server.py
ping -n 3 127.0.0.1 >nul
set PORT=8765
if exist "server.port" for /f "delims=" %%p in (server.port) do set PORT=%%p
start "" "http://localhost:%PORT%/"
start "" /min pythonw nav_sync.pyw
