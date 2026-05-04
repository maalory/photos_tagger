@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if defined LOCALAPPDATA (
    set "RUNTIME_ROOT=%LOCALAPPDATA%\PhotosTagger"
) else (
    set "RUNTIME_ROOT=%USERPROFILE%\.photos_tagger_runtime"
)
set "VENV_DIR=%RUNTIME_ROOT%\venv"

echo.
echo Photos Tagger Launcher
echo =====================
echo Runtime root: %RUNTIME_ROOT%
echo Virtual env : %VENV_DIR%
echo.

if not exist "%RUNTIME_ROOT%" (
    mkdir "%RUNTIME_ROOT%" >nul 2>nul
)
if not exist "%RUNTIME_ROOT%" (
    echo Nepodarilo se vytvorit runtime slozku:
    echo   %RUNTIME_ROOT%
    goto :launcher_error
)

call :ensure_bootstrap_python
if errorlevel 1 goto :launcher_error

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/4] Vytvarim virtualni prostredi mimo projekt...
    call :run_bootstrap -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo Nepodarilo se vytvorit virtualni prostredi:
        echo   %VENV_DIR%
        goto :launcher_error
    )
    echo.
)

set "PYTHON_BIN=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_BIN%" (
    echo Virtualni prostredi bylo ocekavano, ale Python nebyl nalezen:
    echo   %PYTHON_BIN%
    goto :launcher_error
)

echo [2/4] Kontroluji pip...
"%PYTHON_BIN%" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo Pip neni ve virtualnim prostredi dostupny.
    goto :launcher_error
)

echo [3/4] Kontroluji Python zavislosti...
"%PYTHON_BIN%" -c "import importlib.util,sys; missing=[m for m in ('PySide6','PIL') if importlib.util.find_spec(m) is None]; sys.exit(0 if not missing else 2)"
if errorlevel 2 (
    echo Chybi nektere zavislosti. Spoustim instalaci z requirements.txt...
    "%PYTHON_BIN%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Instalace zavislosti selhala.
        goto :launcher_error
    )
)

echo.
echo [4/4] Spoustim aplikaci...
echo.
set "PYTHONPATH=%CD%\src"
"%PYTHON_BIN%" -m photos_tagger.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Aplikace skoncila s chybou %EXIT_CODE%.
    goto :launcher_error_with_code
)

goto :end

:ensure_bootstrap_python
where py >nul 2>nul
if not errorlevel 1 (
    set "BOOTSTRAP_CMD=py -3"
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    set "BOOTSTRAP_CMD=python"
    exit /b 0
)

echo Python 3 nebyl nalezen.
echo.
echo Nainstaluj Python 3 pro Windows a potom spust start.bat znovu.
exit /b 1

:run_bootstrap
if /I "%BOOTSTRAP_CMD%"=="py -3" (
    py -3 %*
    exit /b %ERRORLEVEL%
)

if /I "%BOOTSTRAP_CMD%"=="python" (
    python %*
    exit /b %ERRORLEVEL%
)

exit /b 1

:launcher_error_with_code
pause
endlocal & exit /b %EXIT_CODE%

:launcher_error
pause
endlocal & exit /b 1

:end
endlocal & exit /b 0
