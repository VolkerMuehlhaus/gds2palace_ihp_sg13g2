########################################################################
#
# Copyright 2026 Volker Muehlhaus and IHP PDK Authors
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

# MODEL FOR GMSH WITH PALACE

# Sanity check of the port wall calibration: a zero-length thru.
# A straight TopMetal2 line (15 um wide, 880 um long) over a Metal1 ground strip (220 um wide), with a port wall at
# each end. Both reference planes are shifted by half the line length, to the middle of the line, so that nothing is
# left between them. The ideal result is S11 = 0 and S21 = 1; what remains is the error of ports, calibration and
# reference plane shift together. See "Sanity check: a zero-length thru" in README.md in this folder.
#
# What the GDSII file has (all on purpose 0, one cell 'thru'):
#   - the TopMetal2 line from x = 0 to 880, y = -7.5 to 7.5
#   - the Metal1 ground from x = 0 to 880, y = -110 to 110
#   - a zero-width port line on layer 201 (left) and 202 (right), on the layout edge across the end of the line

import os
import sys
import subprocess

from gds2palace import *


# ======================== workflow settings ================================

# start solver after creating the model? (Linux with Palace installed only)
start_simulation = False
run_command = ['./run_sim']

# ===================== input files and path settings =======================

gds_filename = "zero_length_thru.gds"   # layout with line, ground and port lines
XML_filename = utilities.get_stackup_path('SG13G2_FEM_200um.xml')   # stackup that ships with gds2palace

line_length = 880   # microns, as drawn

# get path for this simulation file
script_path = utilities.get_script_path(__file__)

# use script filename as model basename
model_basename = utilities.get_basename(__file__)

# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename)
print('Simulation data directory: ', sim_path)

# change path to models script path
modelDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(modelDir)

# ======================== simulation settings ================================

settings = {}

settings['unit']   = 1e-6  # geometry is in microns

# Box sides in the order xmin, xmax, ymin, ymax, zmin, zmax.
# xmin and xmax are port walls: PEC at the layout edge, where the line ends. The other sides are absorbing.
settings['boundary'] = ['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC']
settings['margin'] = 200      # dielectric oversize in microns on the sides that are not port walls
settings['air_around'] = 200  # air in microns around the dielectric, on the sides that are not port walls

# Move both reference planes to the middle of the line: a thru of length zero remains.
settings['reference_plane_shift'] = {'xmin': line_length / 2, 'xmax': line_length / 2}

settings['fstart']  = 0e9
settings['fstop']   = 50e9

settings['refined_cellsize'] = 2      # mesh cell size in conductor region
settings['cells_per_wavelength'] = 10 # how many mesh cells per wavelength, must be 10 or more
settings['meshsize_max'] = 100        # microns, override cells_per_wavelength
settings['order'] = 2                 # FEM order
settings['adaptive_mesh_iterations'] = 0

settings['conductor_model'] = 'surface'

# settings['no_gui'] = True  # create files without showing the 3D model


# Ports from GDSII data: a zero-width line on layers 201 and 202, on the layout edge across the end of the line.
# Every port on a port wall must be excited (voltage=1), because the calibration needs the full S-matrix.

simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, target_layername='TopMetal2', direction='x'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, target_layername='TopMetal2', direction='-x'))


# ======================== simulation ================================

# get technology stackup data
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)
# get list of layers from technology
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# read geometries from GDSII, only purpose 0
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, cellname='thru')


########### create model ###########

settings['simulation_ports'] = simulation_ports
settings['materials_list'] = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list'] = metals_list
settings['layernumbers'] = layernumbers
settings['allpolygons'] = allpolygons
settings['sim_path'] = sim_path
settings['model_basename'] = model_basename


# list of ports that are excited (set voltage to zero in port excitation to skip an excitation!)
excite_ports = simulation_ports.all_active_excitations()
config_name, data_dir = simulation_setup.create_palace (excite_ports, settings)


# for convenience, write run script to model directory: it solves the calibration standards first, then the model
utilities.create_run_script(sim_path)


if start_simulation:
    try:
        os.chdir(sim_path)
        subprocess.run(run_command, shell=True)
    except:
        print(f"Unable to run Palace using command ",run_command)
