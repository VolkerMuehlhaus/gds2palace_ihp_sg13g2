# -*- coding: utf-8 -*-

import os, tempfile, platform, sys, importlib

__version__ = "1.0.0"

# ============================== filename and path  =================================

def get_script_path(filename):
    # Define paths and directories
    script_path = os.path.normcase(os.path.dirname(filename))
    return script_path

def get_basename (filename):
    # get file basename without .gds or .py extension
    basename = os.path.basename(filename).replace('.gds', '')
    basename = basename.replace('.py','')
    return basename

def create_sim_path (script_path, model_basename):
    # set directory for simulation output, create path if it does not exist
    base_path = os.path.join(script_path, 'palace_model')

    # check if we might run into path length issues, leave some margin for nested subdiretories and filenames
    if platform.system() == "Windows" and len(base_path) > 200:
        print('[WARNING] Path length limitation, using temp directory for simulation data')
        base_path =  os.path.join(tempfile.gettempdir(), 'palace_model')

    # try to create data directory
    try: 
        sim_path = os.path.join(base_path, model_basename + '_data')
        if not os.path.exists(sim_path):
            os.makedirs(sim_path, exist_ok=True)
    except:
        print('[WARNING] Could not create simulation data directory ', sim_path)
        print('Now trying to use temp directory for simulation data!\n')
        base_path =  os.path.join(tempfile.gettempdir(), 'palace_model')
        sim_path = os.path.join(base_path, model_basename + '_data')

    return sim_path


def create_run_script (destination_path):
    txt = '#!/bin/bash\n'
    txt = txt + 'run_palace config.json\n'
    txt = txt + 'combine_snp\n'

    cmd_filename = os.path.join(destination_path, 'run_sim')
    with open(cmd_filename, "w", newline='\n') as f:  # write with UNIX EOL
        f.write(txt)
    f.close()   


def check_module_version(module_name, expected_version):
    module = importlib.import_module(module_name)
    version = getattr(module, "__version__", None)
    if version is not None:
        if getattr(module, "__version__", None) < expected_version:
            raise RuntimeError(f"{module_name} version mismatch: expected {expected_version}, got {module.__version__}")
    else:
            raise RuntimeError(f"{module_name} does not provide version information, please update!")
