@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM =============================================================================
REM install_gds2palace.bat - one-shot Windows setup for the gds2palace/setupEM
REM workflow, for users with little or no Python experience.
REM
REM What this does:
REM   1. Creates a Python venv on WINDOWS ITSELF (default: %%USERPROFILE%%\venv\palace)
REM      and installs setupEM there (which pulls in gds2palace, gds_prepare_for_EM,
REM      and all their Python dependencies). setupEM's GUI runs natively on
REM      Windows - it is NOT installed inside WSL.
REM   2. Checks whether WSL (Windows Subsystem for Linux) is installed with at
REM      least one Linux distribution. AWS Palace itself is Linux-only, so it
REM      (and the small helper scripts run_palace/combine_snp that setupEM's
REM      Windows->WSL hand-off expects) must live inside WSL, not on Windows.
REM      This script does NOT assume WSL already exists - if it's missing, or
REM      no distro is installed yet, it prints exactly what to run and stops;
REM      re-run this script afterwards to pick up where it left off.
REM   3. If WSL is ready, automatically runs install_palace_wsl.sh inside it to
REM      install AWS Palace (prebuilt Apptainer container) plus run_palace and
REM      combine_snp. This may prompt for your WSL user's sudo password.
REM   4. Prints a short summary and what to do next.
REM
REM Usage:
REM   install_gds2palace.bat [options]
REM
REM Run with NO options at all (the normal double-click case) to get an
REM interactive wizard that asks for venv/scripts locations, whether to add
REM KLayout integration, and whether to set up Palace inside WSL now - each
REM prompt shows its default in brackets, just press Enter to accept it. Any
REM option at all (even just --yes) skips the wizard and uses today's fully
REM automatic, script-friendly behavior instead.
REM
REM Options:
REM   --venv-dir PATH      Where to create the Windows-native Python venv for
REM                        setupEM/gds2palace (default: %%USERPROFILE%%\venv\palace)
REM   --scripts-dir PATH   Where to create the setupEM/run_palace/combine_snp
REM                        launcher scripts, added to your permanent PATH
REM                        (default: %%USERPROFILE%%\scripts)
REM   --wsl-venv-dir PATH  Where to create the small helper venv INSIDE WSL that
REM                        combine_snp uses (default: ~/venv/palace, a Linux
REM                        path - only override with a path that contains no
REM                        spaces)
REM   --palace-version X   Palace container tag to pull inside WSL (default: 016)
REM   --np N               Default core count baked into run_palace inside WSL
REM                        (default: number of CPU cores in WSL, minimum 4)
REM   --skip-palace        Only set up the Windows-native side (venv, setupEM,
REM                        gds2palace); skip the WSL/Palace step entirely
REM   --with-klayout       Also download the KLayout integration helper script
REM   --yes                Non-interactive: skip confirmations inside WSL
REM   -h, --help            Show this help and exit
REM
REM Safe to re-run: every step below is idempotent (skips work that is already
REM done) so you can re-run this after a partial failure, e.g. right after
REM installing WSL for the first time.
REM =============================================================================

set "VENV_DIR=%USERPROFILE%\venv\palace"
set "SCRIPTS_DIR=%USERPROFILE%\scripts"
set "WSL_VENV_DIR="
set "PALACE_VERSION=016"
set "RUN_NP="
set "SKIP_PALACE=0"
set "WITH_KLAYOUT=0"
set "ASSUME_YES=0"

set "GDS2PALACE_REPO_RAW=https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main"
set "SETUPEM_REPO_RAW=https://raw.githubusercontent.com/VolkerMuehlhaus/setupEM/main"
REM install_palace_wsl.sh, install_gds2palace.bat, and install_gds2palace.sh
REM itself are new (added this session) and only exist on the fork's dev
REM branch so far - NOT yet on VolkerMuehlhaus/gds2palace_ihp_sg13g2's main
REM (confirmed 404 there), unlike every other file GDS2PALACE_REPO_RAW
REM points at below, which was already merged upstream and resolves fine.
REM Once these three files are merged upstream (a PR the user hasn't asked
REM for yet), switch this fallback back to "!GDS2PALACE_REPO_RAW!/scripts"
REM like the others and delete this variable.
set "INSTALL_HELPER_REPO_RAW=https://raw.githubusercontent.com/volkermuehlhaus-claude/gds2palace_ihp_sg13g2/dev"
set "UC=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
set "LC=abcdefghijklmnopqrstuvwxyz"

REM ---------------------------------------------------------------------------
REM Option parsing
REM ---------------------------------------------------------------------------

set "NO_ARGS=0"
if "%~1"=="" set "NO_ARGS=1"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--venv-dir"      (set "VENV_DIR=%~2" & shift & shift & goto parse_args)
if /I "%~1"=="--scripts-dir"   (set "SCRIPTS_DIR=%~2" & shift & shift & goto parse_args)
if /I "%~1"=="--wsl-venv-dir"  (set "WSL_VENV_DIR=%~2" & shift & shift & goto parse_args)
if /I "%~1"=="--palace-version" (set "PALACE_VERSION=%~2" & shift & shift & goto parse_args)
if /I "%~1"=="--np"            (set "RUN_NP=%~2" & shift & shift & goto parse_args)
if /I "%~1"=="--skip-palace"   (set "SKIP_PALACE=1" & shift & goto parse_args)
if /I "%~1"=="--with-klayout"  (set "WITH_KLAYOUT=1" & shift & goto parse_args)
if /I "%~1"=="--yes"           (set "ASSUME_YES=1" & shift & goto parse_args)
if /I "%~1"=="-h"              (call :usage & exit /b 0)
if /I "%~1"=="--help"          (call :usage & exit /b 0)
if /I "%~1"=="/?"              (call :usage & exit /b 0)
echo Unknown option: %~1 1>&2
call :usage
exit /b 1
:args_done

REM No options at all (the normal double-click case) drops into an
REM interactive wizard for the handful of settings worth asking about;
REM any option at all (even just --yes) keeps today's fully-automatic,
REM script-friendly behavior with no prompts.
if "!NO_ARGS!"=="1" call :interactive_wizard

REM ---------------------------------------------------------------------------
REM Step 1: locate a Windows-native Python 3.9+
REM ---------------------------------------------------------------------------

call :step "Checking for Python"

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
    call :fail "Python was not found. Install Python 3.9+ from https://www.python.org/downloads/windows/ (check 'Add python.exe to PATH' during install), then re-run this script."
    endlocal
    exit /b 1
)

for /f "delims=" %%V in ('!PYRUN! --version 2^>^&1') do set "PY_VERSION_STR=%%V"
!PYRUN! -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,9) else 1)"
if errorlevel 1 (
    call :fail "Python 3.9+ is required, found !PY_VERSION_STR!. Install a newer Python from https://www.python.org/downloads/windows/ and re-run."
    endlocal
    exit /b 1
)
call :ok "!PY_VERSION_STR! found"

REM ---------------------------------------------------------------------------
REM Step 2: Windows-native venv + setupEM (pulls in gds2palace automatically)
REM ---------------------------------------------------------------------------

call :step "Setting up the Python environment at !VENV_DIR!"

set "PY_EXE=!VENV_DIR!\Scripts\python.exe"
if exist "!PY_EXE!" (
    call :ok "venv already exists, reusing it"
) else (
    !PYRUN! -m venv "!VENV_DIR!"
    if errorlevel 1 (
        call :fail "Could not create venv at !VENV_DIR!"
        endlocal
        exit /b 1
    ) else (
        call :ok "Created venv"
    )
)

"!PY_EXE!" -m pip install --upgrade pip --quiet

call :step "Installing setupEM (this also installs gds2palace, gds_prepare_for_EM, and all Python dependencies - may take a few minutes)"
"!PY_EXE!" -m pip install --upgrade setupEM --quiet
if errorlevel 1 (
    call :fail "pip install setupEM failed - see the error above."
    endlocal
    exit /b 1
)

REM Version numbers are fetched via a tiny helper .py file, and captured by
REM redirecting to a temp file and reading it with set /p, rather than
REM `for /f ... in ('command')` - that construct mis-parses parentheses AND
REM quoted, space-containing paths (like "!PY_EXE!") embedded in the command
REM string, even though the same command runs fine directly.
set "VERCHECK_PY=%TEMP%\_gds2palace_verchk.py"
> "!VERCHECK_PY!" echo import sys
>>"!VERCHECK_PY!" echo mod = __import__(sys.argv[1])
>>"!VERCHECK_PY!" echo print(getattr(mod, "__version__", "unknown"))

set "VERCHECK_OUT=%TEMP%\_gds2palace_verchk.txt"
"!PY_EXE!" "!VERCHECK_PY!" setupEM > "!VERCHECK_OUT!" 2>nul
set /p SETUPEM_VER=<"!VERCHECK_OUT!"
"!PY_EXE!" "!VERCHECK_PY!" gds2palace > "!VERCHECK_OUT!" 2>nul
set /p GDS2PALACE_VER=<"!VERCHECK_OUT!"
del "!VERCHECK_PY!" "!VERCHECK_OUT!" >nul 2>&1
call :ok "setupEM installed: !SETUPEM_VER!"
call :ok "gds2palace installed: !GDS2PALACE_VER!"

REM ---------------------------------------------------------------------------
REM Step 3: launcher scripts (setupEM family, venv activation, run_palace/
REM combine_snp forwarders into WSL) + adding them to the permanent PATH
REM ---------------------------------------------------------------------------

call :step "Creating launcher scripts in !SCRIPTS_DIR!"
if not exist "!SCRIPTS_DIR!" mkdir "!SCRIPTS_DIR!"

for %%N in (setupEM setupThermal stackupEditor resultViewer fieldViewer) do (
    > "!SCRIPTS_DIR!\%%N.bat" echo @echo off
    >>"!SCRIPTS_DIR!\%%N.bat" echo REM Auto-generated by install_gds2palace.bat - launches %%N from the
    >>"!SCRIPTS_DIR!\%%N.bat" echo REM Windows-native venv, without needing to activate it first.
    >>"!SCRIPTS_DIR!\%%N.bat" echo "!VENV_DIR!\Scripts\%%N.exe" %%*
)
call :ok "setupEM, setupThermal, stackupEditor, resultViewer, fieldViewer"

> "!SCRIPTS_DIR!\activate_palace.bat" echo @echo off
>>"!SCRIPTS_DIR!\activate_palace.bat" echo REM Auto-generated by install_gds2palace.bat - activates the venv at
>>"!SCRIPTS_DIR!\activate_palace.bat" echo REM !VENV_DIR! in the CURRENT terminal (run directly, not via 'call').
>>"!SCRIPTS_DIR!\activate_palace.bat" echo call "!VENV_DIR!\Scripts\activate.bat"
call :ok "activate_palace (activates !VENV_DIR! in your current terminal)"

REM run_palace/combine_snp only make sense by forwarding into WSL (Palace
REM itself only runs there) - both operate on the CURRENT directory, the
REM same way setupEM's own "Start Simulation" button does internally
REM (setup_common.py's _windows_to_wsl_path + wsl.exe --cd) and the same way
REM combine_snp already behaves when typed directly inside a WSL terminal
REM (it always searches recursively from its own current directory).
REM
REM Every literal "!" the generated files need (their own delayed-expansion
REM syntax) is written here as "^!" - a doubled "!!" does NOT produce a
REM literal "!" the way "%%" does for a literal "%". An earlier version of
REM this block used "setlocal DisableDelayedExpansion" instead, to avoid the
REM escaping - that turned out to be worse: setlocal/endlocal here corrupted
REM cmd's own parsing state for the rest of this script (confirmed by
REM bisection - a later, unrelated "if" block would misfire), so plain "^!"
REM escaping is used instead despite being more verbose. One exception: the
REM generated files' final "exit /b" uses "%%errorlevel%%" (percent form,
REM no delayed expansion needed for that pseudo-variable), not "^!errorlevel^!"
REM - a caret-escaped "!" as the literal last two characters of an echoed
REM line still gets expanded by the OUTER script despite the escaping
REM (confirmed by testing), so it silently baked in a stale exit code.

> "!SCRIPTS_DIR!\run_palace.bat" echo @echo off
>>"!SCRIPTS_DIR!\run_palace.bat" echo setlocal EnableExtensions EnableDelayedExpansion
>>"!SCRIPTS_DIR!\run_palace.bat" echo REM Auto-generated by install_gds2palace.bat - runs Palace ^(inside WSL^)
>>"!SCRIPTS_DIR!\run_palace.bat" echo REM against the CURRENT directory. Usage: run_palace [configfile]
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "CFG=%%~1"
>>"!SCRIPTS_DIR!\run_palace.bat" echo if "^!CFG^!"=="" set "CFG=config.json"
>>"!SCRIPTS_DIR!\run_palace.bat" echo where wsl.exe ^>nul 2^>^&1
>>"!SCRIPTS_DIR!\run_palace.bat" echo if errorlevel 1 ^(echo ERROR: WSL not found - see install_gds2palace.bat 1^>^&2 ^& exit /b 1^)
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "UC=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "LC=abcdefghijklmnopqrstuvwxyz"
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "WTW_DRIVE=^!CD:~0,1^!"
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "WTW_REST=^!CD:~2^!"
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "WTW_REST=^!WTW_REST:\=/^!"
>>"!SCRIPTS_DIR!\run_palace.bat" echo for /L %%%%i in (0,1,25) do ^(set "WTW_U=^!UC:~%%%%i,1^!" ^& set "WTW_L=^!LC:~%%%%i,1^!" ^& if /I "^!WTW_DRIVE^!"=="^!WTW_U^!" set "WTW_DRIVE=^!WTW_L^!"^)
>>"!SCRIPTS_DIR!\run_palace.bat" echo set "WSL_CWD=/mnt/^!WTW_DRIVE^!^!WTW_REST^!"
>>"!SCRIPTS_DIR!\run_palace.bat" echo wsl.exe --cd "^!WSL_CWD^!" -- bash -lc "run_palace '^!CFG^!'"
>>"!SCRIPTS_DIR!\run_palace.bat" echo exit /b %%errorlevel%%

> "!SCRIPTS_DIR!\combine_snp.bat" echo @echo off
>>"!SCRIPTS_DIR!\combine_snp.bat" echo setlocal EnableExtensions EnableDelayedExpansion
>>"!SCRIPTS_DIR!\combine_snp.bat" echo REM Auto-generated by install_gds2palace.bat - runs combine_snp ^(inside
>>"!SCRIPTS_DIR!\combine_snp.bat" echo REM WSL^) against the CURRENT directory, searching it recursively.
>>"!SCRIPTS_DIR!\combine_snp.bat" echo where wsl.exe ^>nul 2^>^&1
>>"!SCRIPTS_DIR!\combine_snp.bat" echo if errorlevel 1 ^(echo ERROR: WSL not found - see install_gds2palace.bat 1^>^&2 ^& exit /b 1^)
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "UC=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "LC=abcdefghijklmnopqrstuvwxyz"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "WTW_DRIVE=^!CD:~0,1^!"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "WTW_REST=^!CD:~2^!"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "WTW_REST=^!WTW_REST:\=/^!"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo for /L %%%%i in (0,1,25) do ^(set "WTW_U=^!UC:~%%%%i,1^!" ^& set "WTW_L=^!LC:~%%%%i,1^!" ^& if /I "^!WTW_DRIVE^!"=="^!WTW_U^!" set "WTW_DRIVE=^!WTW_L^!"^)
>>"!SCRIPTS_DIR!\combine_snp.bat" echo set "WSL_CWD=/mnt/^!WTW_DRIVE^!^!WTW_REST^!"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo wsl.exe --cd "^!WSL_CWD^!" -- bash -lc "combine_snp"
>>"!SCRIPTS_DIR!\combine_snp.bat" echo exit /b %%errorlevel%%

call :ok "run_palace, combine_snp (forward into WSL, operating on the current directory)"

call :step "Adding !SCRIPTS_DIR! to your permanent PATH"
set "REGOUT=%TEMP%\_gds2palace_regpath.txt"
reg query "HKCU\Environment" /v Path > "!REGOUT!" 2>nul
set "USER_PATH="
for /f "usebackq tokens=1,2,*" %%A in ("!REGOUT!") do if /I "%%A"=="Path" set "USER_PATH=%%C"
del "!REGOUT!" >nul 2>&1

echo "!USER_PATH!" | "%SystemRoot%\System32\find.exe" /I "!SCRIPTS_DIR!" >nul
if not errorlevel 1 (
    call :ok "!SCRIPTS_DIR! is already on your permanent PATH"
) else (
    if "!USER_PATH!"=="" (
        set "NEW_USER_PATH=!SCRIPTS_DIR!"
    ) else (
        set "NEW_USER_PATH=!USER_PATH!;!SCRIPTS_DIR!"
    )
    if not "!NEW_USER_PATH:~1024,1!"=="" (
        call :warn "Your PATH is very long - setx could truncate it. Add !SCRIPTS_DIR! to PATH yourself via System Properties, Environment Variables instead."
    ) else (
        setx PATH "!NEW_USER_PATH!" >nul
        call :ok "Added !SCRIPTS_DIR! to your permanent PATH (open a NEW terminal for this to take effect)"
    )
)

if "!WITH_KLAYOUT!"=="1" (
    call :step "Downloading KLayout integration script"
    where curl >nul 2>&1
    if errorlevel 1 (
        call :warn "curl.exe not found - download manually from !SETUPEM_REPO_RAW!/src/scripts/klayout_setupEM.py"
    ) else (
        curl -fsSL -o "!SCRIPTS_DIR!\klayout_setupEM.py" "!SETUPEM_REPO_RAW!/src/scripts/klayout_setupEM.py"
        call :ok "Saved to !SCRIPTS_DIR!\klayout_setupEM.py - see setupEM README, 'KLayout Integration', to wire this into KLayout's Tools menu."
    )
)

REM ---------------------------------------------------------------------------
REM Step 4: WSL detection + automatic Palace install inside WSL
REM ---------------------------------------------------------------------------
REM
REM This whole step is one nested if/else chain rather than early "goto
REM :summary" exits. A forward goto out of a parenthesized if-block, jumping
REM past OTHER unrelated parenthesized blocks later in the file (as the
REM klayout/launcher/PATH blocks above are), corrupts cmd.exe's parser state
REM and made it execute pieces of those unrelated blocks out of order -
REM confirmed by testing. Nested if/else has no such issue.

if "!SKIP_PALACE!"=="1" (
    call :step "Skipping Palace/WSL setup (--skip-palace)"
    call :warn "You'll need to set up WSL + Palace yourself before you can run simulations - re-run without --skip-palace when ready, or see scripts/install_palace_wsl.sh."
) else (
    call :step "Checking for WSL (Windows Subsystem for Linux)"

    where wsl.exe >nul 2>&1
    if errorlevel 1 (
        call :warn "WSL was not found on this system."
        echo.
        echo     Palace runs inside WSL2, not natively on Windows. This script only
        echo     sets up the Windows-native half ^(setupEM/gds2palace, done above^)
        echo     - to add Palace, do this once:
        echo.
        echo       1. Open PowerShell AS ADMINISTRATOR
        echo       2. Run:   wsl --install
        echo       3. Restart your computer when prompted
        echo       4. Open the new "Ubuntu" app once from the Start menu to finish
        echo          first-time setup ^(choose a UNIX username/password^)
        echo       5. Re-run this script - the Windows part above is already done
        echo          and will be skipped; it will then set up Palace inside WSL
        echo.
        echo     If 'wsl --install' itself fails, your Windows version may be too
        echo     old for WSL2; see https://learn.microsoft.com/en-us/windows/wsl/install
        echo.
    ) else (
        call :ok "wsl.exe found"

        set "WSL_UTF8=1"
        set "WSL_LIST_OUT=%TEMP%\_wsl_list.txt"
        wsl.exe -l -q > "!WSL_LIST_OUT!" 2>nul
        set "WSL_HAS_DISTRO=0"
        for /f "usebackq delims=" %%D in ("!WSL_LIST_OUT!") do set "WSL_HAS_DISTRO=1"
        del "!WSL_LIST_OUT!" >nul 2>&1

        if "!WSL_HAS_DISTRO!"=="0" (
            call :warn "WSL is installed, but no Linux distribution is set up in it yet."
            echo.
            echo     To install one:
            echo       1. Open PowerShell AS ADMINISTRATOR
            echo       2. Run:   wsl --install -d Ubuntu-24.04
            echo       3. Restart your computer if prompted
            echo       4. Open the new "Ubuntu" app once from the Start menu to finish
            echo          first-time setup ^(choose a UNIX username/password^)
            echo       5. Re-run this script - it will then set up Palace inside WSL
            echo.
        ) else (
            call :ok "WSL with at least one Linux distribution found"

            call :step "Setting up Palace inside WSL"

            set "WSL_HELPER_DIR=%~dp0"
            if "!WSL_HELPER_DIR:~-1!"=="\" set "WSL_HELPER_DIR=!WSL_HELPER_DIR:~0,-1!"

            REM NOTE: deliberately NOT restructured into "if errorlevel 1 (
            REM ...) else (...)" here, unlike the venv-creation check in Step
            REM 2 above - that "else" pattern, even though it fixes the exit
            REM CODE for the failure branch too (see :fail's comment),
            REM corrupted execution order elsewhere in this script when
            REM embedded at THIS specific nesting depth (5 levels),
            REM confirmed by bisection. The plain multi-line "if errorlevel 1
            REM (...)" below (no else, just leaving the continuation code as
            REM trailing siblings) does NOT corrupt anything and DOES stop
            REM the script correctly on failure - it may just report exit
            REM code 0 instead of 1 to whatever invoked this .bat, in this
            REM one rare, deeply-nested failure case. Accepted tradeoff: a
            REM correct common/happy path matters far more here.
            if not exist "!WSL_HELPER_DIR!\install_palace_wsl.sh" (
                call :step "Downloading install_palace_wsl.sh helper script"
                where curl >nul 2>&1
                if errorlevel 1 (
                    call :fail "curl.exe not found - cannot download install_palace_wsl.sh. Install curl, or place install_palace_wsl.sh next to this script and re-run."
                    endlocal
                    exit /b 1
                )
                set "WSL_HELPER_DIR=%TEMP%"
                curl -fsSL -o "!WSL_HELPER_DIR!\install_palace_wsl.sh" "!INSTALL_HELPER_REPO_RAW!/scripts/install_palace_wsl.sh"
                if errorlevel 1 (
                    call :fail "Could not download install_palace_wsl.sh. Check your internet connection."
                    endlocal
                    exit /b 1
                )
            )

            call :win_to_wsl_path "!WSL_HELPER_DIR!"
            set "WSL_SCRIPT_DIR=!WSL_PATH!"

            set "WSL_ARGS="
            if "!ASSUME_YES!"=="1" set "WSL_ARGS=!WSL_ARGS! --yes"
            if not "!WSL_VENV_DIR!"=="" set "WSL_ARGS=!WSL_ARGS! --venv-dir !WSL_VENV_DIR!"
            if not "!PALACE_VERSION!"=="" set "WSL_ARGS=!WSL_ARGS! --palace-version !PALACE_VERSION!"
            if not "!RUN_NP!"=="" set "WSL_ARGS=!WSL_ARGS! --np !RUN_NP!"

            call :info "This runs commands inside WSL, including 'sudo apt-get' - you may be prompted for your WSL user's password."
            wsl.exe --cd "!WSL_SCRIPT_DIR!" -- bash -lc "bash ./install_palace_wsl.sh!WSL_ARGS!"
            if errorlevel 1 (
                call :warn "Palace/WSL setup reported an error - see the output above. Fix the issue and re-run this script, or run it directly inside WSL: bash install_palace_wsl.sh"
            ) else (
                call :ok "Palace/WSL setup complete"
            )
        )
    )
)

REM ---------------------------------------------------------------------------
REM Done
REM ---------------------------------------------------------------------------

:summary
call :step "Setup summary"
echo.
echo   What was installed:
echo     - setupEM + gds2palace (Windows-native Python GUI and workflow)  -^> !VENV_DIR!
if "!SKIP_PALACE!"=="1" (
    echo     - AWS Palace / WSL setup                                        -^> skipped ^(--skip-palace^)
) else if "!WSL_HAS_DISTRO!"=="1" (
    echo     - AWS Palace + run_palace/combine_snp                           -^> inside WSL, see output above
) else (
    echo     - AWS Palace / WSL setup                                        -^> NOT done yet, see instructions above
)
echo.
echo   To start working, open a terminal and run:
echo.
echo       "!VENV_DIR!\Scripts\activate.bat"
echo       setupEM
echo.
echo   Re-run this script any time - it will skip anything already done.
exit /b 0

REM ---------------------------------------------------------------------------
REM Subroutines
REM ---------------------------------------------------------------------------

:interactive_wizard
REM No setlocal here (deliberately - see the run_palace.bat/combine_snp.bat
REM generation block above): this subroutine sets VENV_DIR, SCRIPTS_DIR,
REM WITH_KLAYOUT, SKIP_PALACE, PALACE_VERSION and RUN_NP directly in the
REM caller's environment, the same way every other subroutine in this file
REM shares state with the main script.
call :step "No options given - interactive setup. Press Enter to accept each default shown in brackets."
echo.

set "REPLY="
set /p "REPLY=Windows-native Python venv location [!VENV_DIR!]: "
if not "!REPLY!"=="" set "VENV_DIR=!REPLY!"

set "REPLY="
set /p "REPLY=Launcher scripts location, added to your PATH [!SCRIPTS_DIR!]: "
if not "!REPLY!"=="" set "SCRIPTS_DIR=!REPLY!"

set "REPLY="
set /p "REPLY=Also install the KLayout integration script? [y/N]: "
if /I "!REPLY:~0,1!"=="y" set "WITH_KLAYOUT=1"

set "REPLY="
set /p "REPLY=Set up AWS Palace inside WSL now too? [Y/n]: "
if /I "!REPLY:~0,1!"=="n" (
    set "SKIP_PALACE=1"
) else (
    set "REPLY="
    set /p "REPLY=Palace container version [!PALACE_VERSION!]: "
    if not "!REPLY!"=="" set "PALACE_VERSION=!REPLY!"

    set "REPLY="
    set /p "REPLY=Cores for run_palace, blank = auto [auto]: "
    if not "!REPLY!"=="" set "RUN_NP=!REPLY!"
)
echo.
goto :eof

:step
echo.
echo ==^> %~1
goto :eof

:info
echo     %~1
goto :eof

:ok
echo     OK: %~1
goto :eof

:warn
echo     WARN: %~1
goto :eof

:fail
REM Prints the error and returns (its own "exit /b 1" only sets errorlevel
REM and returns to the caller here - a "call"ed label's exit /b does NOT
REM terminate the whole script, confirmed by testing). Every call site MUST
REM follow "call :fail "..."" with "endlocal" then its own "exit /b 1" to
REM actually stop. Two things had to be true together for the exit CODE
REM (not just stopping) to come out right, both confirmed by bisection:
REM   1. "endlocal" right before "exit /b 1" - under an active setlocal,
REM      "exit /b N" 2+ parenthesized blocks deep otherwise loses the real
REM      exit code (process exits 0 instead of N, even though it DOES stop).
REM   2. The "if errorlevel 1 ( call :fail ... exit /b 1 )" must be the LAST
REM      thing in its immediately-enclosing (...) block - if any sibling
REM      statement follows it in that SAME block (even one that can never be
REM      reached, like a trailing "call :ok" after a fail-and-exit branch),
REM      the exit code is lost again. Move any such sibling into its own
REM      "else ( ... )" instead of leaving it as a trailing statement.
echo     ERROR: %~1 1>&2
exit /b 1

:win_to_wsl_path
REM Converts a Windows path like C:\Users\me into /mnt/c/Users/me and
REM returns the result in WSL_PATH. Mirrors setupEM's own
REM _windows_to_wsl_path() (setup_common.py) so paths resolve the same way
REM whether launched from here or from setupEM's own Start Simulation button.
set "WTW_SRC=%~1"
if "!WTW_SRC:~-1!"=="\" set "WTW_SRC=!WTW_SRC:~0,-1!"
set "WTW_DRIVE=!WTW_SRC:~0,1!"
set "WTW_REST=!WTW_SRC:~2!"
set "WTW_REST=!WTW_REST:\=/!"
for /L %%i in (0,1,25) do (
    set "WTW_U=!UC:~%%i,1!"
    set "WTW_L=!LC:~%%i,1!"
    if /I "!WTW_DRIVE!"=="!WTW_U!" set "WTW_DRIVE=!WTW_L!"
)
set "WSL_PATH=/mnt/!WTW_DRIVE!!WTW_REST!"
goto :eof

:usage
echo install_gds2palace.bat - one-shot Windows setup for the gds2palace/setupEM
echo workflow.
echo.
echo What this does:
echo   1. Creates a Python venv on WINDOWS ITSELF (default: %%USERPROFILE%%\venv\palace)
echo      and installs setupEM there (pulls in gds2palace + gds_prepare_for_EM).
echo      setupEM's GUI runs natively on Windows, NOT inside WSL.
echo   2. Checks whether WSL is installed with at least one Linux distro. If
echo      not, prints exactly what to run and stops - re-run afterwards.
echo   3. If WSL is ready, automatically installs AWS Palace ^(prebuilt Apptainer
echo      container^) plus run_palace/combine_snp inside WSL.
echo.
echo Usage:
echo   install_gds2palace.bat [options]
echo.
echo Run with NO options at all for an interactive wizard instead ^(asks for
echo venv/scripts locations, KLayout integration, and whether to set up
echo Palace inside WSL now, with defaults shown in brackets^).
echo.
echo Options:
echo   --venv-dir PATH      Windows-native venv location (default: %%USERPROFILE%%\venv\palace)
echo   --scripts-dir PATH   Launcher scripts location, added to your permanent
echo                        PATH (default: %%USERPROFILE%%\scripts)
echo   --wsl-venv-dir PATH  Helper venv location INSIDE WSL, a Linux path with no
echo                        spaces (default: ~/venv/palace)
echo   --palace-version X   Palace container tag to pull inside WSL (default: 016)
echo   --np N               Default core count baked into run_palace inside WSL
echo   --skip-palace        Only set up the Windows-native side; skip WSL/Palace
echo   --with-klayout       Also download the KLayout integration helper script
echo   --yes                Non-interactive: skip confirmations inside WSL
echo   -h, --help            Show this help and exit
goto :eof
