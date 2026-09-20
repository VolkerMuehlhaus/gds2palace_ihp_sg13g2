@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM =============================================================================
REM install_gds2palace.bat - one-shot Windows setup for the gds2palace/setupEM
REM workflow.
REM
REM This is a THIN STUB: it only checks that Python is present (and downloads
REM its Python companion, install_gds2palace.py, if that isn't already sitting
REM next to it), then hands everything else off there. See install_gds2palace.py
REM for what this actually does, all the options (--venv-dir, --scripts-dir,
REM --skip-palace, --with-klayout, --yes, --help, ...), and the no-options
REM interactive wizard - run "install_gds2palace.bat --help" to see them.
REM
REM Why the logic lives in Python and not here: an earlier all-batch version
REM of this script kept hitting genuinely arcane cmd.exe parser bugs (paren
REM balance mattering even in code that never runs, "set VAR=" with an empty
REM value silently UNSETTING the variable instead of emptying it, "exit /b"
REM losing its exit code several parenthesized blocks deep, ...) that don't
REM exist in Python, which is already a hard requirement for this workflow
REM anyway. This stub only does the two things that were never actually
REM buggy in the old version: checking Python exists, and one curl download.
REM =============================================================================

set "INSTALL_HELPER_REPO_RAW=https://raw.githubusercontent.com/volkermuehlhaus-claude/gds2palace_ihp_sg13g2/dev"

set "PYRUN="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYRUN=py -3"
)
if not defined PYRUN (
    where python >nul 2>&1
    if not errorlevel 1 set "PYRUN=python"
)
if not defined PYRUN (
    echo ERROR: Python was not found. Install Python 3.9+ from https://www.python.org/downloads/windows/ 1>&2
    echo ^(check 'Add python.exe to PATH' during install^), then re-run this script. 1>&2
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

if not exist "!SCRIPT_DIR!\install_gds2palace.py" (
    where curl >nul 2>&1
    if errorlevel 1 (
        echo ERROR: curl.exe not found - cannot download install_gds2palace.py. 1>&2
        echo Install curl, or place install_gds2palace.py next to this script and re-run. 1>&2
        endlocal
        exit /b 1
    )
    echo Downloading install_gds2palace.py ...
    curl -fsSL -o "!SCRIPT_DIR!\install_gds2palace.py" "!INSTALL_HELPER_REPO_RAW!/scripts/install_gds2palace.py"
    if errorlevel 1 (
        echo ERROR: Could not download install_gds2palace.py. Check your internet connection. 1>&2
        endlocal
        exit /b 1
    )
)

!PYRUN! "!SCRIPT_DIR!\install_gds2palace.py" %*
exit /b %errorlevel%
