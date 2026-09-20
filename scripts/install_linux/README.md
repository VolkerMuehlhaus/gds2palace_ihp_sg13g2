# Installing on Linux

← back to [scripts overview](../README.md)

## Do you need this whole repo cloned to install?

No. **install_gds2palace.sh** is fully self-contained and designed to be downloaded (or `curl`'d) on its own, with **no repo checkout required** - it fetches everything else it needs (Python packages from PyPI, helper scripts from this repo's raw GitHub URLs) itself. Download that one file and run it (or `curl -fsSL <raw-url> | bash`). It never needs any other file from this repo to be present locally.

It pulls `setupEM`/`gds2palace` from PyPI, so you always get those from the public package index, not from any local checkout.

## Installing

**install_gds2palace.sh** is the Linux installer - one venv, one machine, no Windows/WSL split needed since Palace runs natively there too. It creates a Python venv (default `~/venv/palace`), installs setupEM (which pulls in gds2palace, gds_prepare_for_EM, and scikit-rf), adds that venv's `bin/` to `PATH` via `~/.profile`, installs AWS Palace itself (prebuilt Apptainer container), and generates `run_palace`/`combine_snp` pointing at it - so `setupEM`, `run_palace` and `combine_snp` are all typeable directly in any new terminal afterward. Works the same on native Linux or inside WSL2. Run `install_gds2palace.sh --help` for all options, or with no options at all for the same kind of interactive wizard as the [Windows installer](../install_windows/README.md). Safe to re-run.

**Before you run it**, you need:

- **Python 3.9+ (`python3`) installed.** The script only *checks* for it - it does not install Python3 itself. If missing, it stops with an install hint (e.g. `sudo apt install python3 python3-venv` on Ubuntu/Debian) and you re-run afterward.
- **Working `sudo` access**, needed for `apt-get` (apt-based distros only) to auto-install anything from this list that's missing: `curl`, the `python3-venv` module, the Qt/XCB runtime libraries the setupEM GUI needs, and Apptainer. `curl`/`python3-venv` install straight away with no prompt beyond the sudo check itself; the Qt libraries and Apptainer ask for confirmation first (`--yes` skips those). Either way, sudo access is validated **once** before any of these run - if this account has none at all, the script fails immediately with the exact command an admin needs to run (e.g. `sudo apt-get install -y curl`). On non-apt distros, or if `sudo`/root access genuinely isn't available, it just tells you what's missing so you can install it yourself.
- If you're piping this script (`curl ... | bash`, see above) **and** any of the above needs a password you haven't already entered recently, note that a piped run has no terminal to prompt with - the sudo check fails immediately rather than hanging, so either run `sudo -v` yourself first or download the script and run it in a normal interactive terminal instead.

**What the script does, automatically:** creates the venv and installs setupEM/gds2palace/scikit-rf into it; adds `$VENV_DIR/bin` to `PATH` via `~/.profile`; installs the Qt/XCB libraries the setupEM GUI needs (apt-based distros); optionally downloads the KLayout integration script (`--with-klayout`); and, unless `--skip-palace`, installs Palace as described below, plus generates `run_palace`/`combine_snp`.

**Where Palace itself comes from:** the script installs [Apptainer](https://apptainer.org/) via the Apptainer PPA (`sudo add-apt-repository ppa:apptainer/ppa`, apt-based distros), then runs `apptainer pull` on a **prebuilt container image published by this repo's maintainer** at `oras://ghcr.io/volkermuehlhaus/palace_016:latest` (GitHub Container Registry) - not an official AWS Palace release artifact, since Palace's own CI doesn't publish a pullable image (see [`doc/building-palace-apptainer.md`](../../doc/building-palace-apptainer.md) for how that image itself gets built, and for building your own instead). It's a multi-GB download, saved to `~/palace_016.sif` and reused on every re-run.

**Left for you, to have a fully working setup:**

- Open a **new** terminal (or `source ~/.profile`) after the script finishes, so the updated PATH takes effect.
- [ParaView](https://www.paraview.org/) if you want to view field-dump results - not installed by this script.
- [KLayout](https://www.klayout.de/) itself, if you want to draw ports or edit layouts in it - same as on Windows, `--with-klayout` only fetches the integration *script*, not KLayout.
- An MPI implementation (OpenMPI or MPICH), only if you plan to use **Elmer's** multi-thread option - not needed for Palace itself.
