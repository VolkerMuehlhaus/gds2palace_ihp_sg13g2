# Installing on Windows + WSL

← back to [scripts overview](../README.md)

## Do I need to clone/download this whole repository to install?

No. **install_gds2palace.bat** is a single downloadable file, designed to be downloaded on its own, with **no repo checkout required**. It fetches everything else it needs: Python packages from PyPI and its own companion helper scripts from this repo's raw GitHub URLs. So a bare copy of just `install_gds2palace.bat` still works - everything else it needs is fetched on demand.

The installation script pulls `setupEM`/`gds2palace` from PyPI, so you always get those from the public package index, not from any local checkout.

## Installing

**install_gds2palace.bat** is a one-shot installer for Windows - a thin `.bat` stub that just checks for Python and then runs **install_gds2palace.py**, where all the actual logic lives.  

The installation script installs setupEM and gds2palace **natively on Windows** in a Python venv, default `%USERPROFILE%\venv\palace`, so gds2palace and its graphical user interface setupEM run on Windows.

For the **Palace solver**, we need the Windows Subsystem for Linux (WSL), because Palace itself is not available on Windows. The installation script will handle this, install Palace to an existing WSL and configure the setupEM GUI to send simulation jobs to the solver that runs inside WSL.

If WSL or a Linux distro isn't installed yet, the installer prints exactly what to run and stops, rather than assuming WSL is already there. Once WSL is ready, it automatically runs **install_palace_wsl.sh** inside it to install Palace (prebuilt Apptainer container) plus the `run_palace`/`combine_snp` helper scripts, matching what setupEM's Windows->WSL hand-off expects to find on the WSL login shell's PATH

Run `install_gds2palace.bat --help` for all options, or run it with no options at all for an interactive wizard (asks for venv/scripts locations, KLayout integration, and whether to set up Palace now, defaults shown in brackets - any option at all skips the wizard). Safe to re-run.

The installer also generates a set of launcher `.bat` files (default `%USERPROFILE%\scripts`, added to your permanent user `PATH`) so none of these need the venv activated first or a full path typed out: `setupEM`, `setupThermal`, `stackupEditor`, `resultViewer`, `fieldViewer`, and Windows-side `run_palace`/`combine_snp` wrappers that forward into WSL against the current directory - the same way setupEM's own "Start Simulation" button does internally - so both work whether typed at a plain Windows prompt or from inside WSL.

It also creates an `activate_palace` command that activates the venv in your current terminal, for running gds2palace from command line rather than setupEM GUI. 

install_palace_wsl.sh can also be run by hand inside an existing WSL/Linux terminal (`bash install_palace_wsl.sh`) if you just want to (re)install the Palace side on its own.

## Requirements

**Before you run the installer script**, you need **Python 3.9+ (`python3`) installed and on your PATH.** This will be checked by the installer.

It is also recommended that you have already configured a WSL environment, so that the installer script can install Palace there. 

**On the WSL side**, you have the same `sudo` requirements as the [Linux installer](../install_linux/README.md) (for `curl`, Apptainer, etc., if any of those are missing inside that WSL distro), but this is usually not an issue, since the account `wsl --install` creates during first-run setup already has sudo access by default.

## What the script does, automatically 
It creates the Windows venv and installs setupEM/gds2palace into it; generates the launcher `.bat` files above and adds them to your PATH; optionally downloads the KLayout integration script (`--with-klayout`); and, once WSL is ready, installs Palace inside WSL as described below, plus generates `run_palace`/`combine_snp` there.

## AWS Palace solver
By default, this installation script also installs the Palace solver into WSL using an Apptainer container image.  

The script installs [Apptainer](https://apptainer.org/) via the Apptainer PPA (`sudo add-apt-repository ppa:apptainer/ppa`, on apt-based distros), then runs `apptainer pull` on a **prebuilt container image published by this repo's maintainer** at `oras://ghcr.io/volkermuehlhaus/palace_016:latest`  

This container image is saved to `~/palace_016.sif` (exact name depends on Palace version) and reused on every re-run. It is not an official AWS Palace release artifact, since Palace's own CI doesn't publish a pullable image. 

If you wish to build a container image yourself, see [`doc/building-palace-apptainer.md`](../../doc/building-palace-apptainer.md) 

## Left for you, to have a fully working setup
When the installation script is finished, these are the remaining steps:

- Open a **new** terminal window after the script finishes, so the updated PATH takes effect.
- If WSL wasn't installed yet, you still need to run the printed `wsl --install` command yourself, reboot, and re-run the script.
- The setupEM GUI includes a simple 3D results viewer to visualize fields. You could install the optional [ParaView](https://www.paraview.org/) tool for a full-featured 3D results viewer.
- The installation script only installs the klayout *integration script*, not the KLayout tool itself.
