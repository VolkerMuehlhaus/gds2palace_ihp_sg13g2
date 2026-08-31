These scripts support the workflow when using gds2palace with the AWS Palace solver. Include the script folder to your PATH.

**build_pypi_readme.py** regenerates `README_pypi.md` at the repo root from `README.md`, rewriting relative `./doc/...` links to absolute GitHub URLs so images render on the PyPI package page. Run this before `python -m build`, from the repo root: `python scripts/build_pypi_readme.py`

**combine_extend_snp.py** is a script to search for Palace S-parameter result files (port-S.csv) and convert them to the standard Touchstone SnP file format. The script will start searching at the current directory, and search through all directory levels below. If S-parameters include low frequency data, it will also run DC data extrapolation to provide a 0 Hz result, and save that into another file with suffix "_dc.snp"
If port geometry information is available, as created by the latest version of gds2palace, an additional file with de-embedded results is created. This is an experimental feature, it adds port de-embedding for lumped ports by cascading negative series L at each port.

**palace_summary.py** prints a human-readable summary of AWS Palace solver results (degrees of freedom, mesh size, simulation time, peak RAM, and adaptive-mesh-refinement error indicators) for a completed or in-progress run. Run it with no arguments from inside the `<model>_data` directory that contains `config.json`, or pass a path as an argument. That path is searched recursively for every `<model>_data` directory (identified by containing a `config.json`) some levels below it, and a summary is printed for each one found - handy for pointing it at a folder of examples and getting a summary of every run inside. The model base name for each run is auto-derived from its directory name (stripping the trailing `_data`); `--model-basename` overrides this, but only applies when exactly one run directory is found. Exits with a nonzero status if any run has no results yet, so it can be chained after `run_palace` in a script to detect whether simulation(s) actually finished.

**combine_snp** is the shell script to run the combine_extend_snp.py Python script, if a Python venv named "palace" exists will all the Python libraries required for the gds2palace workflow, including scikit-rf. Please modify this as required for your environment.

**run_palace** is the script that was used during development to run Palace from an apptainer (container) file ~/palace.sif, using 8 core parallel simulation. Please modify this as required for your environment. A description how to create the Palace apptainer (container) for Palace can be found here: https://awslabs.github.io/palace/stable/install/

If you prefer to install and run Palace in a different way, no problem! The gds2palace workflow creates the input files for Palace, and it is entirely your choice how you run the simulator with these model files, local or on a sophisticated HPC cluster.

---

**run_palace_remote** is a script to run Palace model on a remote machine. This can be used instead of the "normal" run_sim that starts Palace locally. Just **rename the script to run_palace**, to replace the local simulation script. 

To connect the simulation server, the script must be configured once:

- Configure USERNAME, SERVER and TARGETDIR for your actual remote system
- Commands scp and ssh must be configured for passwordless authentication. This stores encryption keys on your system, see https://www.redhat.com/en/blog/passwordless-ssh

Similar to run_palace, this script takes one parameter: the Palace config file *config.json* 
Given the config.json model file, that entire directory (including mesh) is copied to the remote machine, simulated there by running the server's run_sim, and results are copied back when simulation is finished.

This script was successfully used to send simulation from setupEM + gds2palace on MacOS to an Ubuntu simulation server running Ubuntu 24.02.  On the remote system, script run_sim (no parameters) is executed to start Palace for model config.json in the current directory 