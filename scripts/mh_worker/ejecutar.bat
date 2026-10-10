@echo off
REM Mantiene el worker corriendo: si se cae, lo vuelve a levantar a los 15 s.
cd /d "%~dp0"
set /p PY=<python_ruta.txt
:otra
"%PY%" mh_worker.py
ping -n 16 127.0.0.1 >nul
goto otra
