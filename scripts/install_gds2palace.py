#!/usr/bin/env python3
"""
install_gds2palace.py - one-shot Windows setup for the gds2palace/setupEM/
AWS Palace workflow, for users with little or no Python experience.

Normally launched via install_gds2palace.bat (a tiny stub that just checks
Python is present, then hands off here), not run directly - but running it
directly with an already-installed Python works the same way.

What this does:
  1. Creates a Python venv on WINDOWS ITSELF (default: %USERPROFILE%\\venv\\palace)
     and installs setupEM there (which pulls in gds2palace, gds_prepare_for_EM,
     and all their Python dependencies). setupEM's GUI runs natively on
     Windows - it is NOT installed inside WSL.
  2. Generates launcher scripts in %USERPROFILE%\\scripts (setupEM family,
     activate_palace, run_palace/combine_snp - the latter two forward into
     WSL) and adds that folder to your permanent PATH.
  3. Checks whether WSL (Windows Subsystem for Linux) is installed with at
     least one Linux distribution. AWS Palace itself is Linux-only, so it
     must live inside WSL, not on Windows. This script does NOT assume WSL
     already exists - if it's missing, it prints exactly what to run and
     stops; re-run this script afterwards to pick up where it left off.
  4. If WSL is ready, automatically runs install_palace_wsl.sh inside it to
     install AWS Palace (prebuilt Apptainer container) plus run_palace and
     combine_snp there. This may prompt for your WSL user's sudo password.
  5. Prints a short summary and what to do next.

Run with NO options at all for an interactive wizard instead (asks for
venv/scripts locations, KLayout integration, and whether to set up Palace
now, with defaults shown in brackets). Any option at all skips the wizard.

Safe to re-run: every step below is idempotent (skips work that is already
done) so you can re-run this after a partial failure, e.g. right after
installing WSL for the first time.

This is a straight rewrite of an earlier install_gds2palace.bat, done in
Python specifically to get away from cmd.exe/batch: that version kept
hitting genuinely arcane, hard-to-diagnose cmd.exe parser bugs (whole-file
paren balance mattering even in unreached code, forward "goto" out of a
parenthesized block corrupting unrelated code, "set VAR=" with an empty
value silently unsetting the variable rather than emptying it, "exit /b"
losing its exit code N+ blocks deep under an active setlocal...) - none of
which exist in Python. See the fork's git history / CLAUDE.md memory for
the specifics, if curious.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import urllib.request
import winreg
from pathlib import Path

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

if os.name == "nt":
    # Enables ANSI escape processing in the console (a well-known, harmless
    # side effect of this call on Windows) so the color codes below actually
    # render instead of printing as literal escape sequences.
    os.system("")

_BOLD, _GREEN, _YELLOW, _RED, _RESET = "\033[1m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def step(msg: str) -> None:
    print(f"\n{_BOLD}==> {msg}{_RESET}")


def info(msg: str) -> None:
    print(f"    {msg}")


def ok(msg: str) -> None:
    print(f"    {_GREEN}OK:{_RESET} {msg}")


def warn(msg: str) -> None:
    print(f"    {_YELLOW}WARN:{_RESET} {msg}")


def fail(msg: str) -> None:
    print(f"    {_RED}ERROR:{_RESET} {msg}", file=sys.stderr)
    sys.exit(1)


GDS2PALACE_REPO_RAW = "https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main"
SETUPEM_REPO_RAW = "https://raw.githubusercontent.com/VolkerMuehlhaus/setupEM/main"
# install_gds2palace.py/.bat and install_palace_wsl.sh are new (added this
# session) and only exist on the fork's dev branch so far - NOT yet on
# VolkerMuehlhaus/gds2palace_ihp_sg13g2's main. Once merged upstream, switch
# this back to GDS2PALACE_REPO_RAW like everything else and delete this.
INSTALL_HELPER_REPO_RAW = "https://raw.githubusercontent.com/volkermuehlhaus-claude/gds2palace_ihp_sg13g2/dev"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def win_to_wsl_path(path: Path) -> str:
    """Converts a Windows path like C:\\Users\\me into /mnt/c/Users/me.
    Mirrors setupEM's own _windows_to_wsl_path() (setup_common.py) so paths
    resolve the same way whether launched from here or from setupEM's own
    Start Simulation button. Uses os.path.splitdrive rather than hand-rolled
    substring slicing - the batch version of this got a bare drive root
    ("E:\\") wrong in a way that produced a garbled, non-existent path;
    splitdrive handles that correctly for free.
    """
    abs_path = os.path.abspath(str(path))
    drive, rest = os.path.splitdrive(abs_path)
    drive = drive.rstrip(":").lower()
    rest = rest.replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)


def pkg_version(python_exe: Path, package: str) -> str:
    try:
        result = subprocess.run(
            [str(python_exe), "-c",
             f"import importlib.metadata as m; print(m.version('{package}'))"],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Option parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install_gds2palace.py",
        description="One-shot Windows setup for the gds2palace/setupEM/AWS Palace workflow.",
    )
    p.add_argument("--venv-dir", type=Path, default=None,
                    help="Windows-native venv location (default: %%USERPROFILE%%\\venv\\palace)")
    p.add_argument("--scripts-dir", type=Path, default=None,
                    help="Launcher scripts location, added to your permanent PATH "
                         "(default: %%USERPROFILE%%\\scripts)")
    p.add_argument("--wsl-venv-dir", default=None,
                    help="Helper venv location INSIDE WSL, a Linux path (default: ~/venv/palace)")
    p.add_argument("--palace-version", default="016",
                    help="Palace container tag to pull inside WSL (default: 016)")
    p.add_argument("--np", default=None,
                    help="Default core count baked into run_palace inside WSL "
                         "(default: number of CPU cores in WSL, minimum 4)")
    p.add_argument("--skip-palace", action="store_true",
                    help="Only set up the Windows-native side; skip WSL/Palace")
    p.add_argument("--with-klayout", action="store_true",
                    help="Also download the KLayout integration helper script")
    p.add_argument("--yes", action="store_true",
                    help="Non-interactive: skip confirmations inside WSL")
    return p


def interactive_wizard(args: argparse.Namespace) -> None:
    step("No options given - interactive setup. Press Enter to accept each default shown in brackets.")
    print()

    default_venv = args.venv_dir or (Path.home() / "venv" / "palace")
    reply = input(f"Windows-native Python venv location [{default_venv}]: ").strip()
    args.venv_dir = Path(reply) if reply else default_venv

    default_scripts = args.scripts_dir or (Path.home() / "scripts")
    reply = input(f"Launcher scripts location, added to your PATH [{default_scripts}]: ").strip()
    args.scripts_dir = Path(reply) if reply else default_scripts

    reply = input("Also install the KLayout integration script? [y/N]: ").strip().lower()
    if reply.startswith("y"):
        args.with_klayout = True

    reply = input("Set up AWS Palace inside WSL now too? [Y/n]: ").strip().lower()
    if reply.startswith("n"):
        args.skip_palace = True
    else:
        reply = input(f"Palace container version [{args.palace_version}]: ").strip()
        if reply:
            args.palace_version = reply
        reply = input("Cores for run_palace, blank = auto [auto]: ").strip()
        if reply:
            args.np = reply
    print()


# ---------------------------------------------------------------------------
# Step 1: Python version
# ---------------------------------------------------------------------------

def check_python_version() -> None:
    step("Checking Python version")
    if sys.version_info[:2] < (3, 9):
        fail(f"Python 3.9+ is required, found {sys.version.split()[0]}. "
             "Install a newer Python from https://www.python.org/downloads/windows/ and re-run.")
    ok(f"Python {sys.version.split()[0]} found")


# ---------------------------------------------------------------------------
# Step 2: Windows-native venv + setupEM
# ---------------------------------------------------------------------------

def setup_venv(venv_dir: Path) -> Path:
    step(f"Setting up the Python environment at {venv_dir}")
    python_exe = venv_dir / "Scripts" / "python.exe"
    if python_exe.exists():
        ok("venv already exists, reusing it")
    else:
        result = run([sys.executable, "-m", "venv", str(venv_dir)])
        if result.returncode != 0:
            fail(f"Could not create venv at {venv_dir}")
        ok("Created venv")

    run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    step("Installing setupEM (this also installs gds2palace, gds_prepare_for_EM, "
         "and all Python dependencies - may take a few minutes)")
    result = run([str(python_exe), "-m", "pip", "install", "--upgrade", "setupEM", "--quiet"])
    if result.returncode != 0:
        fail("pip install setupEM failed - see the error above.")

    ok(f"setupEM installed: {pkg_version(python_exe, 'setupEM')}")
    ok(f"gds2palace installed: {pkg_version(python_exe, 'gds2palace')}")
    return python_exe


# ---------------------------------------------------------------------------
# Step 3: launcher scripts + PATH
# ---------------------------------------------------------------------------

ENTRY_POINTS = ["setupEM", "setupThermal", "stackupEditor", "resultViewer", "fieldViewer"]

# Shared by the run_palace/combine_snp launchers below: forwards into WSL,
# operating on the CURRENT directory, the same way setupEM's own "Start
# Simulation" button does internally (setup_common.py's
# _windows_to_wsl_path + wsl.exe --cd), and the same way combine_snp already
# behaves when typed directly inside a WSL terminal (it always searches
# recursively from its own current directory).
_WSL_FORWARD_PY = '''\
import os, subprocess, sys

def win_to_wsl_path(path):
    abs_path = os.path.abspath(path)
    drive, rest = os.path.splitdrive(abs_path)
    drive = drive.rstrip(":").lower()
    rest = rest.replace("\\\\", "/")
    return f"/mnt/{{drive}}{{rest}}"

if subprocess.run(["where", "wsl.exe"], capture_output=True).returncode != 0:
    print("ERROR: WSL not found - see install_gds2palace.bat", file=sys.stderr)
    sys.exit(1)

wsl_cwd = win_to_wsl_path(os.getcwd())
{command}
result = subprocess.run(["wsl.exe", "--cd", wsl_cwd, "--", "bash", "-lc", cmd])
sys.exit(result.returncode)
'''

_BAT_STUB = '''@echo off
REM Auto-generated by install_gds2palace.bat - launches the matching .py
REM next to this file with whatever Python is on PATH.
where py >nul 2>&1 && (py -3 "%~dp0{name}.py" %*) || (python "%~dp0{name}.py" %*)
'''


def write_launchers(scripts_dir: Path, venv_dir: Path) -> None:
    step(f"Creating launcher scripts in {scripts_dir}")
    scripts_dir.mkdir(parents=True, exist_ok=True)

    for name in ENTRY_POINTS:
        (scripts_dir / f"{name}.bat").write_text(
            "@echo off\r\n"
            f"REM Auto-generated by install_gds2palace.bat - launches {name} from the\r\n"
            "REM Windows-native venv, without needing to activate it first.\r\n"
            f'"{venv_dir}\\Scripts\\{name}.exe" %*\r\n',
            encoding="utf-8",
        )
    ok(", ".join(ENTRY_POINTS))

    (scripts_dir / "activate_palace.bat").write_text(
        "@echo off\r\n"
        "REM Auto-generated by install_gds2palace.bat - activates the venv at\r\n"
        f"REM {venv_dir} in the CURRENT terminal (run directly, not via 'call').\r\n"
        f'call "{venv_dir}\\Scripts\\activate.bat"\r\n',
        encoding="utf-8",
    )
    ok(f"activate_palace (activates {venv_dir} in your current terminal)")

    run_palace_cmd = (
        'cfg = sys.argv[1] if len(sys.argv) > 1 else "config.json"\n'
        'cmd = f"run_palace \'{cfg}\'"'
    )
    combine_snp_cmd = 'cmd = "combine_snp"'

    (scripts_dir / "run_palace.py").write_text(
        _WSL_FORWARD_PY.format(command=run_palace_cmd), encoding="utf-8")
    (scripts_dir / "run_palace.bat").write_text(
        _BAT_STUB.format(name="run_palace"), encoding="utf-8")
    (scripts_dir / "combine_snp.py").write_text(
        _WSL_FORWARD_PY.format(command=combine_snp_cmd), encoding="utf-8")
    (scripts_dir / "combine_snp.bat").write_text(
        _BAT_STUB.format(name="combine_snp"), encoding="utf-8")
    ok("run_palace, combine_snp (forward into WSL, operating on the current directory)")


def add_to_permanent_path(scripts_dir: Path) -> None:
    step(f"Adding {scripts_dir} to your permanent PATH")
    scripts_str = str(scripts_dir)

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                         winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, value_type = "", winreg.REG_EXPAND_SZ

        if any(p.strip().lower() == scripts_str.lower() for p in current.split(";")):
            ok(f"{scripts_dir} is already on your permanent PATH")
            return

        new_value = f"{current};{scripts_str}" if current else scripts_str
        winreg.SetValueEx(key, "Path", 0, value_type, new_value)

    # Best-effort: tell other top-level windows the environment changed, so
    # e.g. a File Explorer opened after this might pick it up without a full
    # logoff. Already-open terminals still need to be reopened regardless -
    # that part isn't something any process can do to another.
    try:
        HWND_BROADCAST, WM_SETTINGCHANGE = 0xFFFF, 0x1A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 0, 5000, None)
    except Exception:
        pass

    ok(f"Added {scripts_dir} to your permanent PATH (open a NEW terminal for this to take effect)")


def maybe_download_klayout_script(scripts_dir: Path) -> None:
    step("Downloading KLayout integration script")
    try:
        download(f"{SETUPEM_REPO_RAW}/src/scripts/klayout_setupEM.py",
                 scripts_dir / "klayout_setupEM.py")
        ok(f"Saved to {scripts_dir}\\klayout_setupEM.py - see setupEM README, "
           "'KLayout Integration', to wire this into KLayout's Tools menu.")
    except Exception as e:
        warn(f"Could not download klayout_setupEM.py: {e}")


# ---------------------------------------------------------------------------
# Step 4: WSL detection + Palace install
# ---------------------------------------------------------------------------

def find_wsl_exe() -> str | None:
    for name in ("wsl.exe", "wsl"):
        result = run(["where", name], capture_output=True, text=True)
        if result.returncode == 0:
            return name
    return None


def list_wsl_distros() -> list[str]:
    env = os.environ.copy()
    env["WSL_UTF8"] = "1"
    try:
        result = run(["wsl.exe", "-l", "-q"], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", env=env, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def setup_palace_in_wsl(args: argparse.Namespace, script_dir: Path) -> bool:
    """Returns True if a distro was found (regardless of whether the Palace
    install itself then succeeded), False if WSL/distro setup is still
    needed - the caller uses this to word the final summary correctly."""
    step("Checking for WSL (Windows Subsystem for Linux)")

    wsl_cmd = find_wsl_exe()
    if wsl_cmd is None:
        warn("WSL was not found on this system.")
        print()
        print("    Palace runs inside WSL2, not natively on Windows. This script only")
        print("    sets up the Windows-native half (setupEM/gds2palace, done above)")
        print("    - to add Palace, do this once:")
        print()
        print("      1. Open PowerShell AS ADMINISTRATOR")
        print("      2. Run:   wsl --install")
        print("      3. Restart your computer when prompted")
        print('      4. Open the new "Ubuntu" app once from the Start menu to finish')
        print("         first-time setup (choose a UNIX username/password)")
        print("      5. Re-run this script - the Windows part above is already done")
        print("         and will be skipped; it will then set up Palace inside WSL")
        print()
        print("    If 'wsl --install' itself fails, your Windows version may be too")
        print("    old for WSL2; see https://learn.microsoft.com/en-us/windows/wsl/install")
        print()
        return False
    ok("wsl.exe found")

    distros = list_wsl_distros()
    if not distros:
        warn("WSL is installed, but no Linux distribution is set up in it yet.")
        print()
        print("    To install one:")
        print("      1. Open PowerShell AS ADMINISTRATOR")
        print("      2. Run:   wsl --install -d Ubuntu-24.04")
        print("      3. Restart your computer if prompted")
        print('      4. Open the new "Ubuntu" app once from the Start menu to finish')
        print("         first-time setup (choose a UNIX username/password)")
        print("      5. Re-run this script - it will then set up Palace inside WSL")
        print()
        return False
    ok("WSL with at least one Linux distribution found")

    step("Setting up Palace inside WSL")

    helper_dir = script_dir
    helper_path = helper_dir / "install_palace_wsl.sh"
    if not helper_path.exists():
        step("Downloading install_palace_wsl.sh helper script")
        helper_dir = Path(os.environ.get("TEMP", "."))
        helper_path = helper_dir / "install_palace_wsl.sh"
        try:
            download(f"{INSTALL_HELPER_REPO_RAW}/scripts/install_palace_wsl.sh", helper_path)
        except Exception as e:
            fail(f"Could not download install_palace_wsl.sh: {e}")

    wsl_script_dir = win_to_wsl_path(helper_dir)

    wsl_args = []
    if args.yes:
        wsl_args.append("--yes")
    if args.wsl_venv_dir:
        wsl_args += ["--venv-dir", args.wsl_venv_dir]
    if args.palace_version:
        wsl_args += ["--palace-version", args.palace_version]
    if args.np:
        wsl_args += ["--np", args.np]

    info("This runs commands inside WSL, including 'sudo apt-get' - you may be "
         "prompted for your WSL user's password.")
    bash_cmd = "bash ./install_palace_wsl.sh" + "".join(f" {a}" for a in wsl_args)
    result = run(["wsl.exe", "--cd", wsl_script_dir, "--", "bash", "-lc", bash_cmd])
    if result.returncode != 0:
        warn("Palace/WSL setup reported an error - see the output above. Fix the "
             "issue and re-run this script, or run it directly inside WSL: "
             "bash install_palace_wsl.sh")
    else:
        ok("Palace/WSL setup complete")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if len(sys.argv) == 1:
        interactive_wizard(args)

    if args.venv_dir is None:
        args.venv_dir = Path.home() / "venv" / "palace"
    if args.scripts_dir is None:
        args.scripts_dir = Path.home() / "scripts"

    check_python_version()
    python_exe = setup_venv(args.venv_dir)
    write_launchers(args.scripts_dir, args.venv_dir)
    add_to_permanent_path(args.scripts_dir)
    if args.with_klayout:
        maybe_download_klayout_script(args.scripts_dir)

    script_dir = Path(__file__).resolve().parent
    wsl_distro_found = False
    if args.skip_palace:
        step("Skipping Palace/WSL setup (--skip-palace)")
        warn("You'll need to set up WSL + Palace yourself before you can run "
             "simulations - re-run without --skip-palace when ready, or see "
             "scripts/install_palace_wsl.sh.")
    else:
        wsl_distro_found = setup_palace_in_wsl(args, script_dir)

    step("Setup summary")
    print()
    print("  What was installed:")
    print(f"    - setupEM + gds2palace (Windows-native Python GUI and workflow)  -> {args.venv_dir}")
    if args.skip_palace:
        print("    - AWS Palace / WSL setup                                        -> skipped (--skip-palace)")
    elif wsl_distro_found:
        print("    - AWS Palace + run_palace/combine_snp                           -> inside WSL, see output above")
    else:
        print("    - AWS Palace / WSL setup                                        -> NOT done yet, see instructions above")
    print()
    print("  To start working, open a terminal and run:")
    print()
    print(f'      "{args.venv_dir}\\Scripts\\activate.bat"')
    print("      setupEM")
    print()
    print("  Re-run this script any time - it will skip anything already done.")


if __name__ == "__main__":
    main()
