@echo off
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env
  echo Fichier .env cree. Renseigne TENANT_ID, CLIENT_ID et CLIENT_SECRET puis relance.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
