@echo off
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo Ejecuta este archivo como administrador: clic derecho, "Ejecutar como administrador".
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo No se encontro Python. Instalalo desde python.org marcando "Add python.exe to PATH" y repite.
  pause
  exit /b 1
)
for /f "delims=" %%i in ('where python') do (
  echo %%i> python_ruta.txt
  goto :encontrado
)
:encontrado
python -m pip install --quiet requests
if not exist worker.env (
  copy worker.env.example worker.env >nul
  echo Se creo worker.env. Completa LEARNIX_URL y MH_RELAY_TOKEN, guarda, cierra el Bloc de notas y vuelve a ejecutar este instalador.
  notepad worker.env
  pause
  exit /b 0
)
echo Comprobando conexion con Learnix y con Hacienda...
python mh_worker.py --probar
if errorlevel 1 (
  echo.
  echo La prueba fallo. Corrige lo indicado arriba y vuelve a ejecutar este instalador.
  pause
  exit /b 1
)
REM Que el equipo no se suspenda ni hiberne mientras esta enchufado.
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
REM Tarea que arranca con Windows (sin necesidad de iniciar sesion).
schtasks /Create /TN "LearnixMHWorker" /TR "\"%~dp0ejecutar.bat\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
  echo No se pudo crear la tarea programada.
  pause
  exit /b 1
)
schtasks /Run /TN "LearnixMHWorker"
echo.
echo Listo. El worker esta corriendo y arrancara solo cada vez que se encienda el equipo.
echo Registro: %~dp0logs\mh_worker.log
pause
