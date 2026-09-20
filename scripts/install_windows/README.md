# Installing on Windows + WSL

← back to [scripts overview](../README.md)

## Do you need this whole repo cloned to install?

No. **install_gds2palace.bat** is a single downloadable file, designed to be downloaded (or `curl`'d) on its own, with **no repo checkout required** - it fetches everything else it needs (Python packages from PyPI, its own companion helper scripts from this repo's raw GitHub URLs) itself: it's a thin stub that only checks that Python is present, then hands off to **install_gds2palace.py** (downloading that file next to itself first if it's not already there) - all the actual installer logic lives in the `.py` file, not in batch. That in turn downloads its own companion **install_palace_wsl.sh** into `%TEMP%` and runs it via WSL for the Palace/WSL leg. So a bare, on-its-own copy of just `install_gds2palace.bat` still works - everything else it needs is fetched on demand.

It pulls `setupEM`/`gds2palace` from PyPI, so you always get those from the public package index, not from any local checkout.

## Installing

**install_gds2palace.bat** is a one-shot installer for Windows - a thin `.bat` stub that just checks for Python and then runs **install_gds2palace.py**, where all the actual logic lives (see that file's own module docstring for why: an earlier all-batch version kept hitting genuinely arcane cmd.exe parser bugs that don't exist in Python, which is already a hard requirement for this workflow anyway). It installs setupEM and gds2palace natively on Windows (a Python venv, default `%USERPROFILE%\venv\palace`) - the GUI itself never runs inside WSL. AWS Palace is Linux-only, so the script separately checks for WSL (Windows Subsystem for Linux); if WSL or a Linux distro isn't installed yet, it prints exactly what to run and stops, rather than assuming WSL is already there. Once WSL is ready, it automatically runs **install_palace_wsl.sh** inside it to install Palace (prebuilt Apptainer container) plus the `run_palace`/`combine_snp` helper scripts, matching what setupEM's Windows->WSL hand-off expects to find on the WSL login shell's PATH. Run `install_gds2palace.bat --help` for all options, or run it with no options at all for an interactive wizard (asks for venv/scripts locations, KLayout integration, and whether to set up Palace now, defaults shown in brackets - any option at all skips the wizard). Safe to re-run.

It also generates a set of launcher `.bat` files (default `%USERPROFILE%\scripts`, added to your permanent user `PATH`) so none of these need the venv activated first or a full path typed out: `setupEM`, `setupThermal`, `stackupEditor`, `resultViewer`, `fieldViewer` (each just launches that entry point from the Windows-native venv), `activate_palace` (activates the venv in your current terminal), and Windows-side `run_palace`/`combine_snp` wrappers that forward into WSL against the current directory - the same way setupEM's own "Start Simulation" button does internally - so both work whether typed at a plain Windows prompt or from inside WSL.

install_palace_wsl.sh can also be run by hand inside an existing WSL/Linux terminal (`bash install_palace_wsl.sh`) if you just want to (re)install the Palace side on its own.

> **Note (temporary):** as of this writing, `install_gds2palace.bat`/`.py` and `install_palace_wsl.sh` only exist on this fork's `dev` branch, not yet on the upstream `VolkerMuehlhaus/gds2palace_ihp_sg13g2` repo - so the `.bat`'s and `.py`'s self-download fallbacks above currently point at the fork, not upstream (see the `INSTALL_HELPER_REPO_RAW` constant near the top of each script). Once these files are merged upstream, that should switch back to the same upstream URL every other download in these scripts already uses.

**Before you run it**, you need:

- **Python 3.9+ installed and on PATH.** The script only *checks* for `py`/`python` - it does not install Python itself. If missing, it stops with a link to [python.org](https://www.python.org/downloads/windows/) and a reminder to check "Add python.exe to PATH" during that install, then re-run this script.
- `curl.exe` (used to download helper files) ships with Windows 10 1803+/11 by default. WSL itself is *not* a prerequisite: if it's missing, the script tells you the exact commands to run (`wsl --install`, a reboot, opening the new Ubuntu app once) and stops; re-running the script afterward picks up where it left off. That one-time `wsl --install` step needs an elevated PowerShell - nothing on the Windows side of this script needs admin rights.
- **On the WSL side**, once it hands off there: the same `sudo` requirements as the [Linux installer](../install_linux/README.md) (for `curl`, Apptainer, etc., if any of those are missing inside that WSL distro) - not usually an issue, since the account `wsl --install` creates during first-run setup already has sudo access by default, but worth knowing if you're running this under a WSL distro/account that was locked down afterward.

**What the script does, automatically:** creates the Windows venv and installs setupEM/gds2palace into it; generates the launcher `.bat` files above and adds them to your PATH; optionally downloads the KLayout integration script (`--with-klayout`); and, once WSL is ready, installs Palace inside WSL as described below, plus generates `run_palace`/`combine_snp` there.

**Where Palace itself comes from:** the script installs [Apptainer](https://apptainer.org/) inside WSL via the Apptainer PPA (`sudo add-apt-repository ppa:apptainer/ppa`, apt-based distros), then runs `apptainer pull` on a **prebuilt container image published by this repo's maintainer** at `oras://ghcr.io/volkermuehlhaus/palace_016:latest` (GitHub Container Registry) - not an official AWS Palace release artifact, since Palace's own CI doesn't publish a pullable image (see [`doc/building-palace-apptainer.md`](../../doc/building-palace-apptainer.md) for how that image itself gets built, and for building your own instead). It's a multi-GB download, saved to `~/palace_016.sif` inside WSL and reused on every re-run.

**Left for you, to have a fully working setup:**

- Open a **new** terminal window after the script finishes, so the updated PATH takes effect.
- If WSL wasn't installed yet, you still need to run the printed `wsl --install` command yourself, reboot, and re-run the script.
- [ParaView](https://www.paraview.org/) if you want to view field-dump results (Palace/Elmer EM field plots) - not installed by this script.
- [KLayout](https://www.klayout.de/) itself, if you want to draw ports or edit layouts in it - `--with-klayout` only downloads the small integration *script* that wires gds2palace's port picker into an *existing* KLayout install, it does not install KLayout.
- [Microsoft MPI](https://learn.microsoft.com/en-us/message-passing-interface/microsoft-mpi), only if you plan to use **Elmer's** multi-thread option (`settings['ELMER_MPI_THREADS']`) - not needed for Palace itself.
