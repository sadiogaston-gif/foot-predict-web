@echo off
rem ---------------------------------------------------------------------------
rem  Foot Predict - Lancement complet (backend + frontend)
rem
rem  Double-cliquez sur ce fichier : deux fenetres s'ouvrent.
rem    - Backend  : http://127.0.0.1:8011  (documentation : /docs)
rem    - Frontend : http://localhost:3000
rem
rem  Pour tout arreter : fermez les deux fenetres ouvertes.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
echo Ouverture du backend et du frontend...
start "Foot Predict - Backend" "%~dp0start_backend.bat"
start "Foot Predict - Frontend" "%~dp0frontend\start_frontend.bat"
echo.
echo Backend  : http://127.0.0.1:8011/docs
echo Frontend : http://localhost:3000
echo.
echo Fermez les deux fenetres pour arreter l'application.
timeout /t 4 >nul
