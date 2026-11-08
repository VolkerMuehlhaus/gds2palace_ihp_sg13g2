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

import os
import sys
import subprocess

# we expect gds2palace in the same directory as this model file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))
from gds2palace import *

# Model comments
#
# Calibrated ports at port walls: a differential GSSG line on TopMetal2, 300 um long, with a port wall at both ends.
# A port wall is a box side set to 'PORTWALL': a PEC wall right at the layout edge. The ports on it are removed from
# the result by calibration (see "Calibrated de-embedding at port walls" in the user guide).
#
# What the GDSII file has:
#   1. the lines drawn to the layout edge
#   2. a port polygon on the layout edge over the end of each line, 1 um deep: that is the gap between the PEC wall
#      and the line, which gds2palace cuts out of the line (a zero-width line along the edge also works, the gap is
#      then set by the tool)
#   3. ground strips that reach the layout edge next to the lines
#
# gds2palace writes the model and two calibration standards (thru lines of 200 and 400 um with the cross-section at
# the wall) into the same folder; both ends share them. run_sim solves the standards first, then the model, and
# combine_snp writes line_gssg_portwall_deembedded.s4p with the ports removed, and line_gssg_portwall_deembedding.json
# with the line at the wall (Z0, n_eff and loss per mode).


# ======================== workflow settings ================================

#start solver after creating the model?
start_simulation = False
run_command = ['./run_sim']

# ===================== input files and path settings =======================

gds_filename = "line_gssg_portwall.gds"   # geometries
XML_filename = "../XML_stackup/latest/IHP/SG13G2_FEM_200um.xml"          # stackup

# merge via polygons with distance less than .. microns, set to 0 to disable via merging.
merge_polygon_size = 0

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
settings['margin'] = 100   # distance in microns from GDSII geometry boundary to simulation boundary (not on port walls)
settings['air_around'] = 50

# xmin and xmax are port walls: PEC at the layout edge, no oversize and no air there (set by gds2palace)
settings['boundary'] = ['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC']

# optional: move the reference plane into the layout along the feed, per port wall, in microns
# settings['reference_plane_shift'] = {'xmin': 50, 'xmax': 50}

settings['fstart']  = 0e9
settings['fstop']   = 100e9
settings['fstep']   = 2.5e9

settings['refined_cellsize'] = 2  # mesh cell size in conductor region
settings['cells_per_wavelength'] = 10   # how many mesh cells per wavelength, must be 10 or more

settings['meshsize_max'] = 70  # microns, override cells_per_wavelength
settings['adaptive_mesh_iterations'] = 0

# settings['no_gui'] = True  # create files without showing 3D model


# Ports from GDSII Data, polygon geometry from specified special layer
# Every port on a port wall must be excited: the calibration needs the full S-matrix.
# The direction is set by gds2palace for ports on a port wall (into the layout).

simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, target_layername='TopMetal2', direction='x'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, target_layername='TopMetal2', direction='x'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=3, voltage=1, port_Z0=50, source_layernum=203, target_layername='TopMetal2', direction='-x'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=4, voltage=1, port_Z0=50, source_layernum=204, target_layername='TopMetal2', direction='-x'))


# ======================== simulation ================================

# get technology stackup data
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)
# get list of layers from technology
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# read geometries from GDSII, only purpose 0
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, merge_polygon_size=merge_polygon_size)


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


# for convenience, write run script to model directory: it solves the calibration standards first
utilities.create_run_script(sim_path)


if start_simulation:
    try:
        os.chdir(sim_path)
        subprocess.run(run_command, shell=True)
    except:
        print(f"Unable to run Palace using command ",run_command)
