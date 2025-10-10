@echo off
setlocal EnableExtensions
REM Avvia Planny (Flask + openpyxl) con venv, poi apre il browser.

REM ---- Vai nella cartella di questo .bat ----
cd /d "%~dp0"

REM ---- CONFIG BROWSER (il server.py usa 127.0.0.1:8000) ----
set "HOST=127.0.0.1"
set "PORT=8000"

REM ---- TROVA PYTHON ----
set "PY_EXE="
for %%P in (py.exe python.exe) do (
  where %%P >nul 2>&1 && set "PY_EXE=%%P" && goto :gotpy
)
for %%D in (
  "%LocalAppData%\Programs\Python\Python312"
  "%LocalAppData%\Programs\Python\Python311"
  "C:\Program Files\Python312"
  "C:\Program Files\Python311"
  "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312"
  "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311"
) do (
  if exist "%%~D\python.exe" set "PY_EXE=%%~D\python.exe" & goto :gotpy
)

echo.
echo [ERRORE] Python non trovato.
echo 1) Installa Python 3.x: https://www.python.org/downloads/
echo    (spuntare "Add python.exe to PATH" e "Install launcher (py)").
echo 2) Oppure: winget install -e --id Python.Python.3.12
echo.
pause
exit /b 1

:gotpy
echo Using Python: %PY_EXE%

REM ---- CREA VENV SE MANCANTE ----
if not exist ".venv\Scripts\python.exe" (
  "%PY_EXE%" -m venv ".venv" || goto :fail
)

REM ---- AGGIORNA PIP + INSTALLA DIPENDENZE ----
".\.venv\Scripts\python.exe" -m pip install -U pip || goto :fail
".\.venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail

REM ---- AVVIA SERVER (MINIMIZZATO) ----
start "Planny Server" /min ".\.venv\Scripts\python.exe" "server.py"

REM Attendi un attimo e apri il browser
timeout /t 1 >nul
start "" "http://%HOST%:%PORT%/"

exit /b 0

:fail
echo.
echo [ERRORE] Installazione o avvio falliti. Controlla i messaggi sopra.
pause
exit /b 1
