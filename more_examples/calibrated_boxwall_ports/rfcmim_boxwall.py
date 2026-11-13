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

# An IHP SG13G2 rfcmim capacitor (30 x 15 um, feed width 10 um), simulated with calibrated ports at port walls
# ("box wall ports"), so that the result is the capacitor alone, without feed lines and without port parasitics.
# See README.md in this folder for the step-by-step description.
#
# What the GDSII file has (all on purpose 0, flat, one cell 'rfcmim'):
#   - the rfcmim pcell, from x = 3.62 to 44.82 um
#   - a 35 um feed line at each terminal, 10 um wide: TopMetal1 to the left edge (x = -31.38),
#     Metal5 to the right edge (x = 79.82)
#   - a Metal1 ground plane that reaches both edges
#   - a zero-width port line on layer 201 (left) and 202 (right), on the layout edge across the end of each feed line
#
# The left and right box sides are port walls: PEC walls right at the layout edge. gds2palace cuts a small gap
# between the wall and each line, places the port in that gap, and writes two calibration standards per wall
# (thru lines of length L and 2 L with the cross-section at the wall). run_sim solves them before the model, and
# combine_snp removes the port by double delay calibration and then the 35 um feed lines (reference plane shift).

import os
import sys
import subprocess

from gds2palace import *


# ======================== workflow settings ================================

# start solver after creating the model? (Linux with Palace installed only)
start_simulation = False
run_command = ['./run_sim']

# ===================== input files and path settings =======================

gds_filename = "rfcmim_boxwall.gds"   # layout with feed lines, ground and port lines
XML_filename = utilities.get_stackup_path('SG13G2_FEM_200um.xml')   # stackup that ships with gds2palace

# merge via polygons with distance less than .. microns: the Vmim via array becomes one block
merge_polygon_size = 2

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
# xmin and xmax are port walls: PEC at the layout edge, where the feed lines end. gds2palace sets margin and
# air to 0 on these two sides by itself. The other sides are absorbing boundaries as usual.
settings['boundary'] = ['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC']
settings['margin'] = 20      # dielectric oversize in microns on the sides that are not port walls
settings['air_around'] = 20  # air in microns around the dielectric, on the sides that are not port walls

# Move the reference planes 35 um into the layout along the feed lines, to the edge of the pcell.
# The result is then the capacitor alone, as the PDK model describes it.
settings['reference_plane_shift'] = {'xmin': 35, 'xmax': 35}

settings['fstart']  = 0e9
settings['fstop']   = 180e9

settings['refined_cellsize'] = 0.5    # mesh cell size in conductor region
settings['cells_per_wavelength'] = 10 # how many mesh cells per wavelength, must be 10 or more
settings['meshsize_max'] = 100        # microns, override cells_per_wavelength
settings['order'] = 2                 # FEM order
settings['adaptive_mesh_iterations'] = 0

settings['conductor_model'] = 'solve_inside'  # mesh inside the metals: best for a MIM capacitor's series resistance

# settings['no_gui'] = True  # create files without showing the 3D model


# Ports from GDSII data: a zero-width line on layers 201 and 202, on the layout edge across the end of each feed line.
# Every port on a port wall must be excited (voltage=1), because the calibration needs the full S-matrix.
# On a port wall, gds2palace sets the direction itself (into the layout), so the direction given here doesn't matter.

simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, target_layername='TopMetal1', direction='x'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, target_layername='Metal5', direction='-x'))


# ======================== simulation ================================

# get technology stackup data
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)
# get list of layers from technology
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# read geometries from GDSII, only purpose 0
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, merge_polygon_size=merge_polygon_size, cellname='rfcmim')


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
