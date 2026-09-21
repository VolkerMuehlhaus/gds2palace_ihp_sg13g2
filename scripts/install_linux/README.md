# Installing on Linux

← back to [scripts overview](../README.md)

## Do I need to clone/download this whole repository to install?

No. **install_gds2palace.sh** is fully self-contained and designed to be downloaded on its own, with **no repo checkout required**. It fetches everything else it needs: Python packages from PyPI and helper scripts from this repo's raw GitHub URLs. Simply download that one file and run it. It never needs any other file from this repo to be present locally.

The installation script pulls `setupEM`/`gds2palace` from PyPI, so you always get those from the public package index, not from any local checkout.

## Installing

**install_gds2palace.sh** is the Linux installer, installing both the gds2palace workflow and the Palace solver.  If you have sudo access, it will install almost all missing components automatically, otherwise please read the "before you run" notes below and ask your admin to install the required components first.

- For the Python part of the workflow, it creates a Python venv (default `~/venv/palace`), installs setupEM with gds2palace, gds_prepare_for_EM, and scikit-rf
- It adds that venv's `bin/` to `PATH` via `~/.profile`, so `setupEM`, `run_palace` and `combine_snp` are all typeable directly in any new terminal afterward  
- It generates `run_palace`/`combine_snp` scripts to start Palace and postprocess results    
- It installs AWS Palace itself (prebuilt Apptainer container)  

If you run `install_gds2palace.sh` with no options, you will be guided through the installation options, asking for target directories etc. You can stop at any time and re-run again later, existing parts of the installation will be maintained.

You can also run `install_gds2palace.sh --help` for all command line options, if you prefer this.

## Requirements
**Before you run the installer script**, you need **Python 3.9+ (`python3`) installed.** This will be checked by the installer.

If you have **working `sudo` access**, the installation script will install the software listed below using `apt-get`, if it is missing.  
- `curl`  
- the `python3-venv` module
- the Qt/XCB runtime libraries
- [Apptainer](https://apptainer.org/)  

sudo access is validated **once** before any of these run - if this account has none at all, the script fails immediately with the exact command an admin needs to run (e.g. `sudo apt-get install -y curl`). On non-apt distros, or if `sudo`/root access genuinely isn't available, it just tells you what's missing so you can install it yourself.

If you do **not have working `sudo` access**, please ask your system administrator to install the required components first.

## AWS Palace solver
By default, this installation script also installs the Palace solver using an Apptainer container image.  

The script installs [Apptainer](https://apptainer.org/) via the Apptainer PPA (`sudo add-apt-repository ppa:apptainer/ppa`, on apt-based distros), then runs `apptainer pull` on a **prebuilt container image published by this repo's maintainer** at `oras://ghcr.io/volkermuehlhaus/palace_016:latest`  

This container image is saved to `~/palace_016.sif` (exact name depends on Palace version) and reused on every re-run. It is not an official AWS Palace release artifact, since Palace's own CI doesn't publish a pullable image. 

If you wish to build a container image yourself, see [`doc/building-palace-apptainer.md`](../../doc/building-palace-apptainer.md) 

## Left for you, to have a fully working setup
When the installation script is finished, these are the remaining steps:

- Open a **new** terminal (or `source ~/.profile`) after the script finishes, so the updated PATH takes effect.
- The setupEM GUI includes a simple 3D results viewer to visualize fields. You could install the optional [ParaView](https://www.paraview.org/) tool for a full-featured 3D results viewer.
- The installation script only installs the klayout *integration script*, not the KLayout tool itself.
