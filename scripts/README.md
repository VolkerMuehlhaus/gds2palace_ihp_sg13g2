These scripts support the workflow when using gds2palace with the AWS Palace solver.

combine_extend_snp.py is a script to search for Palace S-parameter result files (port-S.csv) and convert them to the standard Touchstone SnP file format. The script will start searching at the current directory, and search through all directory levels below. If S-parameters include low frequency data, it will also run DC data extrapolation to provide a 0 Hz result, and save that into another file with suffix "_dc.snp"
If port geometry information is available, as created by the latest version of gds2palace, an additional file with de-embedded results is created. This is an experimental feature, it adds port de-embedding for lumped ports by cascading negative series L at each port.

combine_snp is the shell script to run the combine_extend_snp.py Python script, if a Python venv named "palace" exists will all the Python libraries required for the gds2palace workflow, including scikit-rf. Please modify this as required for your environment.

run_palace is the script that was used during development to run Palace from an apptainer (container) file ~/palace.sif, using 8 core parallel simulation. Please modify this as required for your environment. A description how to create the Palace apptainer (container) for Palace can be found here: https://awslabs.github.io/palace/stable/install/

If you prefer to install and run Palace in a different way, no problem! The gds2palace workflow creates the input files for Palace, and it is entirely your choice how you run the simulator with these model files, local or on a sophisticated HPC cluster.