These scripts support the workflow when using gds2palace with the AWS Palace solver. Include the script folder to your PATH.

## Installing on Windows

**install_gds2palace.bat** is a one-shot installer for Windows. It installs setupEM and gds2palace natively on Windows (a Python venv, default `%USERPROFILE%\venv\palace`) - the GUI itself never runs inside WSL. AWS Palace is Linux-only, so the script separately checks for WSL (Windows Subsystem for Linux); if WSL or a Linux distro isn't installed yet, it prints exactly what to run and stops, rather than assuming WSL is already there. Once WSL is ready, it automatically runs **install_palace_wsl.sh** inside it to install Palace (prebuilt Apptainer container) plus the `run_palace`/`combine_snp` helper scripts, matching what setupEM's Windows->WSL hand-off expects to find on the WSL login shell's PATH. Run `install_gds2palace.bat --help` for all options, or run it with no options at all for an interactive wizard (asks for venv/scripts locations, KLayout integration, and whether to set up Palace now, defaults shown in brackets - any option at all skips the wizard). Safe to re-run.

It also generates a set of launcher `.bat` files (default `%USERPROFILE%\scripts`, added to your permanent user `PATH`) so none of these need the venv activated first or a full path typed out: `setupEM`, `setupThermal`, `stackupEditor`, `resultViewer`, `fieldViewer` (each just launches that entry point from the Windows-native venv), `activate_palace` (activates the venv in your current terminal), and Windows-side `run_palace`/`combine_snp` wrappers that forward into WSL against the current directory - the same way setupEM's own "Start Simulation" button does internally - so both work whether typed at a plain Windows prompt or from inside WSL.

install_palace_wsl.sh can also be run by hand inside an existing WSL/Linux terminal (`bash install_palace_wsl.sh`) if you just want to (re)install the Palace side on its own.

**Before you run it**, you need:

- **Python 3.9+ installed and on PATH.** The script only *checks* for `py`/`python` - it does not install Python itself. If missing, it stops with a link to [python.org](https://www.python.org/downloads/windows/) and a reminder to check "Add python.exe to PATH" during that install, then re-run this script.
- Nothing else - `curl.exe` (used to download helper files) ships with Windows 10 1803+/11 by default. WSL itself is *not* a prerequisite: if it's missing, the script tells you the exact commands to run (`wsl --install`, a reboot, opening the new Ubuntu app once) and stops; re-running the script afterward picks up where it left off. That one-time `wsl --install` step needs an elevated PowerShell - nothing else the script does needs admin rights.

**What the script does, automatically:** creates the Windows venv and installs setupEM/gds2palace into it; generates the launcher `.bat` files above and adds them to your PATH; optionally downloads the KLayout integration script (`--with-klayout`); and, once WSL is ready, installs Apptainer + pulls the Palace container + generates `run_palace`/`combine_snp` inside WSL.

**Left for you, to have a fully working setup:**

- Open a **new** terminal window after the script finishes, so the updated PATH takes effect.
- If WSL wasn't installed yet, you still need to run the printed `wsl --install` command yourself, reboot, and re-run the script.
- [ParaView](https://www.paraview.org/) if you want to view field-dump results (Palace/Elmer EM field plots) - not installed by this script.
- [KLayout](https://www.klayout.de/) itself, if you want to draw ports or edit layouts in it - `--with-klayout` only downloads the small integration *script* that wires gds2palace's port picker into an *existing* KLayout install, it does not install KLayout.
- [Microsoft MPI](https://learn.microsoft.com/en-us/message-passing-interface/microsoft-mpi), only if you plan to use **Elmer's** multi-thread option (`settings['ELMER_MPI_THREADS']`) - not needed for Palace itself.

## Installing on Linux

**install_gds2palace.sh** is the Linux equivalent - one venv, one machine, no Windows/WSL split needed since Palace runs natively there too. It creates a Python venv (default `~/venv/palace`), installs setupEM (which pulls in gds2palace, gds_prepare_for_EM, and scikit-rf), adds that venv's `bin/` to `PATH` via `~/.profile`, installs AWS Palace itself (prebuilt Apptainer container), and generates `run_palace`/`combine_snp` pointing at it - so `setupEM`, `run_palace` and `combine_snp` are all typeable directly in any new terminal afterward. Works the same on native Linux or inside WSL2. Run `install_gds2palace.sh --help` for all options, or with no options at all for the same kind of interactive wizard as the Windows installer. Safe to re-run.

**Before you run it**, you need:

- **Python 3.9+ (`python3`) installed.** The script only *checks* for it - it does not install Python3 itself. If missing, it stops with an install hint (e.g. `sudo apt install python3 python3-venv` on Ubuntu/Debian) and you re-run afterward. It *will* auto-install the `python3-venv` module itself via `apt-get` if `python3` is present but that module isn't (apt-based distros only, asks first unless `--yes`).
- **Working `sudo` access**, needed for `apt-get` (Qt/XCB runtime libraries for the setupEM GUI, and Apptainer) - the script asks before each `sudo` action unless `--yes` is given, and only on apt-based distros; on other distros it just warns you to install the equivalent packages yourself if something's missing.
- `curl`, normally preinstalled on most distros already.

**What the script does, automatically:** creates the venv and installs setupEM/gds2palace/scikit-rf into it; adds `$VENV_DIR/bin` to `PATH` via `~/.profile`; installs the Qt/XCB libraries the setupEM GUI needs (apt-based distros); optionally downloads the KLayout integration script (`--with-klayout`); and, unless `--skip-palace`, installs Apptainer + pulls the Palace container + generates `run_palace`/`combine_snp`.

**Left for you, to have a fully working setup:**

- Open a **new** terminal (or `source ~/.profile`) after the script finishes, so the updated PATH takes effect.
- [ParaView](https://www.paraview.org/) if you want to view field-dump results - not installed by this script.
- [KLayout](https://www.klayout.de/) itself, if you want to draw ports or edit layouts in it - same as on Windows, `--with-klayout` only fetches the integration *script*, not KLayout.
- An MPI implementation (OpenMPI or MPICH), only if you plan to use **Elmer's** multi-thread option - not needed for Palace itself.

## Running Palace

**combine_extend_snp.py** is a script to search for Palace S-parameter result files (port-S.csv) and convert them to the standard Touchstone SnP file format. The script will start searching at the current directory, and search through all directory levels below. If S-parameters include low frequency data, it will also run DC data extrapolation to provide a 0 Hz result, and save that into another file with suffix "_dc.snp"
If port geometry information is available, as created by the latest version of gds2palace, an additional file with de-embedded results is created. This is an experimental feature, it adds port de-embedding for lumped ports by cascading negative series L at each port.

**combine_snp** is the shell script to run the combine_extend_snp.py Python script, if a Python venv named "palace" exists will all the Python libraries required for the gds2palace workflow, including scikit-rf. Please modify this as required for your environment.

**run_palace** is the script that was used during development to run Palace from an apptainer (container) file ~/palace.sif, using 8 core parallel simulation. Please modify this as required for your environment.  

If you prefer to install and run Palace in a different way, no problem! The gds2palace workflow creates the input files for Palace, and it is entirely your choice how you run the simulator with these model files, local or on a sophisticated HPC cluster.

---

**run_palace_remote** is a script to run Palace model on a remote machine. This can be used instead of the "normal" run_sim that starts Palace locally. Just **rename the script to run_palace**, to replace the local simulation script. 

To connect the simulation server, the script must be configured once:

- Configure USERNAME, SERVER and TARGETDIR for your actual remote system
- Commands scp and ssh must be configured for passwordless authentication. This stores encryption keys on your system, see https://www.redhat.com/en/blog/passwordless-ssh

Similar to run_palace, this script takes one parameter: the Palace config file *config.json* 
Given the config.json model file, that entire directory (including mesh) is copied to the remote machine, simulated there by running the server's run_sim, and results are copied back when simulation is finished.

This script was successfully used to send simulation from setupEM + gds2palace on MacOS to an Ubuntu simulation server running Ubuntu 24.02.  On the remote system, script run_sim (no parameters) is executed to start Palace for model config.json in the current directory 


## Show simulation log / report

**palace_summary.py** prints a human-readable summary of AWS Palace solver results for a completed or in-progress run. 

-  degrees of freedom
- mesh size
- simulation time
- peak RAM
- adaptive-mesh-refinement error indicators 

Run `palace_summary.py` with no arguments from inside the `<model>_data` directory that contains `config.json`, or pass a path as an argument. That path is searched recursively for every `<model>_data` directory (identified by containing a `config.json`).  

The model base name for each run is auto-derived from its directory name, or you can override by `--model-basename`. 

palace_summary.py exits with a nonzero status if any run has no results yet, so it can be chained after `run_palace` in a script to detect whether simulation(s) actually finished.

## Other Utilities

**build_pypi_readme.py** regenerates `README_pypi.md` at the repo root from `README.md`, rewriting relative `./doc/...` links to absolute GitHub URLs so images render on the PyPI package page. Run this before `python -m build`, from the repo root: `python scripts/build_pypi_readme.py`
