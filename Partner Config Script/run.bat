@echo off
setlocal

:: Cambiar al directorio del script
cd /d "%~dp0"

echo ============================================================
echo   Automatizacion Diaria Drive/BigQuery -> Preptime -> Seamless
echo ============================================================

:: 1. Verificar si existe el entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Creando entorno virtual 'venv'...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [SETUP] Instalando dependencias desde requirements.txt...
    pip install -r requirements.txt
    echo [SETUP] Instalando binarios de Playwright Chromium...
    playwright install chromium
) else (
    call venv\Scripts\activate.bat
)

:: 2. Ejecutar el pipeline principal
echo [RUN] Iniciando pipeline de procesamiento...
python main.py %*

set EXIT_CODE=%ERRORLEVEL%
echo.
if %EXIT_CODE% NEQ 0 (
    echo ============================================================
    echo [ERROR] La ejecucion finalizo con errores (Codigo %EXIT_CODE%).
    echo Revisa el archivo de log en data/logs/ para mas informacion.
    echo ============================================================
) else (
    echo ============================================================
    echo [EXITO] Proceso completado correctamente.
    echo ============================================================
)

exit /b %EXIT_CODE%
