########################################################################
#
# Copyright 2025 Volker Muehlhaus and IHP PDK Authors
#
# Licensed under the GNU General Public License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.gnu.org/licenses/gpl-3.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################

# -*- coding: utf-8 -*-

import os, tempfile, platform, sys, importlib
from . import util_elmer 

__version__ = "1.1.0"

# ============================== filename and path  =================================

def get_script_path(filename):
    """Get path from full filename
    Args:
        filename (string): full filename inclduing path
    Returns:
        string: path only
    """

    # Define paths and directories
    script_path = os.path.normcase(os.path.dirname(filename))
    return script_path


def get_basename (filename):
    """Remove suffix .py or .gds from filename
    Args:
        filename (string): filename including suffix
    Returns:
        string: filename without suffix
    """

    # get file basename without .gds or .py extension
    basename = os.path.basename(filename).replace('.gds', '')
    basename = basename.replace('.py','')
    return basename

def create_sim_path (script_path, model_basename, dirname='palace_model'):
    """set directory for simulation output, create path if it does not exist. 

    Args:
        script_path (string): path where simulation script is located
        model_basename (string): base name to be used for naming output directory

    Returns:
        _type_: _description_
    """
    # set directory for simulation output, create path if it does not exist
    base_path = os.path.join(script_path, dirname)

    # check if we might run into path length issues, leave some margin for nested subdiretories and filenames
    if platform.system() == "Windows" and len(base_path) > 200:
        print('[WARNING] Path length limitation, using temp directory for simulation data')
        base_path =  os.path.join(tempfile.gettempdir(), dirname)

    # try to create data directory
    try: 
        sim_path = os.path.join(base_path, model_basename + '_data')
        if not os.path.exists(sim_path):
            os.makedirs(sim_path, exist_ok=True)
    except:
        print('[WARNING] Could not create simulation data directory ', sim_path)
        print('Now trying to use temp directory for simulation data!\n')
        base_path =  os.path.join(tempfile.gettempdir(), dirname)
        sim_path = os.path.join(base_path, model_basename + '_data')

    return sim_path


def create_run_script (destination_path):
    """Create run script that can be used to start Palace simulation and then run postprocessing
    Args:
        destination_path (string): target path for run script file
    """
    txt = '#!/bin/bash\n'
    txt = txt + 'run_palace config.json\n'
    txt = txt + 'combine_snp\n'

    cmd_filename = os.path.join(destination_path, 'run_sim')
    with open(cmd_filename, "w", newline='\n') as f:  # write with UNIX EOL
        f.write(txt)
    f.close()   
    
    if sys.platform.startswith("linux"):
        # make it executable
        os.chmod(cmd_filename, 0o755)        


def create_elmer_run_script (destination_path, settings):
    """Create run script that can be used to start Elmer simulation and then run postprocessing
    Args:
        destination_path (string): target path for run script file
        settings (dict): dictionary of model settings, we need to check multithreading setting here
    """

    ELMER_MPI_THREADS = util_elmer.get_ELMER_MPI_THREADS(settings)

    if ELMER_MPI_THREADS==1:
        txt = '#!/bin/bash\n'
        txt = txt + 'ElmerSolver\n'
        txt = txt + 'combine_snp\n'
    else:
        txt = '#!/bin/bash\n'
        txt = txt + f'mpirun -np {ELMER_MPI_THREADS} ElmerSolver case.sif\n'
        txt = txt + 'combine_snp\n'

    cmd_filename = os.path.join(destination_path, 'run_elmer')
    with open(cmd_filename, "w", newline='\n') as f:  # write with UNIX EOL
        f.write(txt)
    f.close()       


def check_module_version(module_name, expected_version):
    """Check version of a module
    Args:
        module_name (string): name of module
        expected_version (_type_): expected module version

    Raises:
        RuntimeError: version mismatch
        RuntimeError: does not provide version information
    """
    module = importlib.import_module(module_name)
    version = getattr(module, "__version__", None)
    if version is not None:
        if getattr(module, "__version__", None) < expected_version:
            raise RuntimeError(f"{module_name} version mismatch: expected {expected_version}, got {module.__version__}")
    else:
            raise RuntimeError(f"{module_name} does not provide version information, please update!")
