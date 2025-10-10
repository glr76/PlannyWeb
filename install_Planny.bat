@echo off

setlocal ENABLEDELAYEDEXPANSION

title Installazione Planny (fix pip/utente)
 
REM ===== Lavora sempre nella cartella del .bat =====

cd /d "%~dp0"
 
echo ===============================

echo   Installazione Planny (Win)

echo ===============================

echo.
 
REM ===== Rimuovi SEMPRE la venv per evitare pip sporco =====

if exist ".venv" (

  echo [INFO] Rimuovo vecchia venv per rigenerare pip/pointer...

  rmdir /s /q ".venv"

)
 
REM ===== Trova Python (launcher) =====

set "PYFOUND="

where py >nul 2>nul && set "PYFOUND=1"
 
set "TRY1=py -3.13 -m venv .venv"

set "TRY2=py -3 -m venv .venv"

set "TRY3=python -m venv .venv"
 
echo [1/5] Creo venv...

if defined PYFOUND (

  call %TRY1% || call %TRY2% || call %TRY3%

) else (

  call %TRY3%

)
 
if not exist ".venv\Scripts\python.exe" (

  echo [ERRORE] Creazione venv fallita.

  pause

  exit /b 1

)
 
echo [OK] Venv creata.
 
REM ===== Attiva venv =====

call ".venv\Scripts\activate.bat" || (

  echo [ERRORE] Attivazione venv fallita.

  pause

  exit /b 1

)
 
REM ===== Rigenera pip nella venv ed evita shims vecchi =====

echo [2/5] Rigenero pip con ensurepip...

python -m ensurepip --upgrade
 
echo [3/5] Aggiorno pip/setuptools/wheel (via python -m pip)...

python -m pip install --upgrade pip setuptools wheel
 
REM ===== Crea requirements se manca =====

if not exist "requirements.txt" (

  echo [INFO] requirements.txt non trovato: lo creo...
> requirements.txt echo Flask>=2.3
>> requirements.txt echo openpyxl>=3.1

)
 
echo [4/5] Installo requirements (via python -m pip)...

python -m pip install -r requirements.txt

if errorlevel 1 (

  echo [ERRORE] Installazione requirements fallita.

  type requirements.txt

  pause

  exit /b 1

)
 
REM ===== Avvia server =====

echo [5/5] Avvio server...

start "" http://127.0.0.1:8000

python server.py
 
echo [FINE] Tutto ok.

pause

endlocal

 