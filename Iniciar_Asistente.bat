@echo off
title Asistente Juridico - Estudio Segovia
chcp 65001 >nul

echo ==================================================
echo   Iniciando Asistente Juridico...
echo ==================================================

:: Carpeta donde está este .bat (funciona sin importar dónde se copie
:: la carpeta ni en qué máquina o usuario de Windows se ejecute).
cd /d "%~dp0"

:: Arranca el servidor en SU PROPIA ventana (queda abierta como log).
:: Ya NO hay que apretar ENTER aca: la pausa se hace desde el dashboard.
start "Asistente (servidor)" cmd /k python servidor.py

:: Espera unos segundos y abre el panel en el navegador
timeout /t 3 >nul
start http://localhost:8000

exit
