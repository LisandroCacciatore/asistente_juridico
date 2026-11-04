@echo off
title Portal del Estudio - Segovia
chcp 65001 >nul

:: Carpeta donde está este .bat (funciona sin importar dónde se copie
:: la carpeta ni en qué máquina o usuario de Windows se ejecute).
cd /d "%~dp0"

:: El portal necesita config.py: ahí están PORTAL_SECRETO, la base y
:: las personas. Sin eso el login no puede funcionar.
if not exist config.py goto falta_config

:: Si YA hay un portal corriendo en el 8100, no arranques un segundo:
:: el segundo no puede tomar el puerto y muere con un error rojo.
:: En vez de eso, abrí el panel: el que está corriendo es el que sirve.
netstat -ano | findstr /r /c:"127.0.0.1:8100 .*LISTENING" >nul 2>&1
if not errorlevel 1 goto ya_corre

echo ==================================================
echo   Preparando la base del portal...
echo ==================================================
python portal_admin.py init
if errorlevel 1 goto error_base

:: El login firma la cookie con PORTAL_SECRETO. Si sigue el placeholder,
:: mejor avisarlo acá que mostrar un error al entrar.
python -c "from portal import auth; auth.firmar_cookie('prueba')" >nul 2>&1
if errorlevel 1 goto error_secreto

echo ==================================================
echo   Iniciando Portal del Estudio...
echo ==================================================
start "Portal (servidor)" cmd /k python -u -m portal.servidor_portal
timeout /t 3 >nul
start http://127.0.0.1:8100
exit

:ya_corre
echo ==================================================
echo   El portal YA esta corriendo.
echo   Abriendo el panel en el navegador...
echo ==================================================
timeout /t 2 >nul
start http://127.0.0.1:8100
exit

:falta_config
echo ==================================================
echo   Falta config.py.
echo   Copia config.example.py a config.py y completa
echo   PORTAL_SECRETO antes de arrancar el portal.
echo ==================================================
pause
exit /b 1

:error_secreto
echo ==================================================
echo   PORTAL_SECRETO no esta configurado.
echo   Copia config.example.py a config.py y genera una
echo   clave real (ver docs/PORTAL.md).
echo ==================================================
pause
exit /b 1

:error_base
echo ==================================================
echo   No se pudo preparar la base del portal.
echo   Revisa el error de arriba (config.py, permisos o
echo   una base bloqueada por otro proceso).
echo ==================================================
pause
exit /b 1
