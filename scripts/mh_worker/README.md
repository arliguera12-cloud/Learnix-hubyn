# Worker de consultas a Hacienda

Hacienda responde 403 a las peticiones que salen de Railway. Este worker corre en
un equipo con internet de El Salvador, consulta a Hacienda por Learnix y le
devuelve el resultado al backend. Flujo completo en `backend/utils/mh_relay.py`.

El worker **no tiene claves de Supabase**: solo la URL del backend y un token
(`MH_RELAY_TOKEN`) que se revoca cambiando la variable.

## Puesta en marcha (una vez)

**1. Base de datos.** En Supabase → SQL Editor, ejecuta `db/12_mh_consulta_cola.sql`.

**2. Token.** En la consola de Railway (o en cualquier equipo con Python):
`python -c "import secrets; print(secrets.token_urlsafe(48))"` — copia el resultado.

**3. Variables en Railway** (servicio del backend):
`MH_RELAY_TOKEN` = el token · `MH_CONSULTA_MODO` = `relay`. Deja que redespliegue.

**4. El equipo.** Instala Python 3.8 o superior desde python.org marcando
*Add python.exe to PATH*. Copia la carpeta `scripts/mh_worker` al equipo.

**5. Instalar.** Clic derecho en `instalar.bat` → *Ejecutar como administrador*.
La primera vez crea `worker.env` y lo abre: pon `LEARNIX_URL` (dirección pública
del backend en Railway) y el mismo `MH_RELAY_TOKEN`. Guarda y vuelve a ejecutar
`instalar.bat`: comprueba el token y Hacienda, evita la suspensión, y deja el
worker como tarea que arranca con Windows.

Registro: `logs\mh_worker.log`. Para quitarlo: `desinstalar.bat` (como administrador).

## Comprobar que funciona
- `python mh_worker.py --probar` imprime `[OK]` en backend y en Hacienda.
- Procesa un lote en Learnix y en los logs de Railway busca `Consulta MH (relay) OK`.

## Operación
- Mantén el equipo encendido y con internet. Si se apaga, Learnix sigue procesando
  con regex/Visión/IA; los DTE quedan en cola y se verifican al volver.
- Windows Update puede reiniciar el equipo: la tarea arranca sola al encender.
- Cambiar el token: nueva variable en Railway + `worker.env`, y reiniciar el equipo
  (o `schtasks /End` y `/Run` sobre `LearnixMHWorker`).
- Limpieza ocasional de la cola: `DELETE FROM mh_consulta_cola WHERE actualizado_en < NOW() - INTERVAL '30 days';`

## Pruebas
`python test_mh_worker.py` (sin red). Backend: `python backend/tests/test_mh_relay.py`.
