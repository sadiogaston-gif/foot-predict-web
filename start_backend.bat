@echo off
rem ---------------------------------------------------------------------------
rem  Foot Predict - Backend (FastAPI)
rem  Double-cliquez sur ce fichier pour lancer l'API sur le port 8011.
rem  Documentation interactive : http://127.0.0.1:8011/docs
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

netstat -ano | findstr ":8011" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo Le backend est deja en cours d'execution sur le port 8011.
  echo Fermez d'abord l'ancienne fenetre si vous voulez le redemarrer.
  pause
  exit /b 0
)

echo Demarrage du backend Foot Predict sur http://127.0.0.1:8011 ...
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8011
pause
