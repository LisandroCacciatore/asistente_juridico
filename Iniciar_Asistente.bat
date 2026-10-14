@echo off
title Asistente Juridico - Estudio Segovia
chcp 65001 >nul

:: Carpeta donde está este .bat (funciona sin importar dónde se copie
:: la carpeta ni en qué máquina o usuario de Windows se ejecute).
cd /d "%~dp0"

:: Si YA hay un asistente corriendo en el 8000, no arranques un segundo:
:: el segundo no puede tomar el puerto, muere con un error rojo que asusta
:: y no explica nada, y encima parece que "no arrancó". En vez de eso,
:: abrí el panel: el que está corriendo es el que te sirve.
:: (Se pregunta con un solo `if` por línea, sin bloques entre paréntesis:
::  así el .bat funciona aunque cambien los finales de línea.)
netstat -ano | findstr /r /c:"127.0.0.1:8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 goto ya_corre

echo ==================================================
echo   Iniciando Asistente Juridico...
echo ==================================================

:: Arranca el servidor en SU PROPIA ventana (queda abierta como log).
:: Ya NO hay que apretar ENTER aca: la pausa se hace desde el dashboard.
start "Asistente (servidor)" cmd /k python -u servidor.py

:: Espera unos segundos y abre el panel en el navegador
timeout /t 3 >nul
start http://localhost:8000
exit

:ya_corre
echo ==================================================
echo   El asistente YA esta corriendo.
echo   Abriendo el panel en el navegador...
echo ==================================================
timeout /t 2 >nul
start http://localhost:8000
exit
