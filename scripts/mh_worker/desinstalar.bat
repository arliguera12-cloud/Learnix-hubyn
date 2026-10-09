@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Ejecuta este archivo como administrador.
  pause
  exit /b 1
)
schtasks /End /TN "LearnixMHWorker" >nul 2>&1
schtasks /Delete /TN "LearnixMHWorker" /F
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *mh_worker*" >nul 2>&1
echo Worker desinstalado. Si sigue algun python.exe abierto, reinicia el equipo.
pause
