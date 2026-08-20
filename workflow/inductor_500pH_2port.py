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

# Model for IHP OpenPDK EM workflow created using setupEM
import os, sys, subprocess

from gds2palace import *

# get path for this simulation file
script_path = utilities.get_script_path(__file__)
# use script filename as model basename
model_basename = utilities.get_basename(__file__)
# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename)

# ========================= workflow settings ==========================
# preview model/mesh only, without running solver?
start_simulation = False

# Command to start simulation
# run_command = ['start', 'wsl.exe']  # Windows Subsystem for Linux
run_command = ['./run_sim']         # Linux

# ===================== input files and settings =======================
settings={}
settings['GdsFile'] = 'inductor_500pH_with_ports.gds'
settings['SubstrateFile'] = 'SG13G2_200um.xml'
settings['preprocess_gds'] = True  # preprocess GDSII for safe handling of cutouts/holes
settings['merge_polygon_size'] = 0.0   # merge via polygons with distance less than .. microns, set to 0 to disable via merging.
settings['purpose'] = [0]  # GDSII data type that is read from file (all other data type is skipped)
settings['fstart'] = 0.0e9
settings['fstop'] = 100.0e9
settings['refined_cellsize'] = 3.0  # mesh cell size in conductor region
settings['cells_per_wavelength'] = 10.0  # how many mesh cells per wavelength, must be 10 or more
settings['meshsize_max'] = 100.0	# absolute limit in micron for mesh size, in addition to cells/wavelength
settings['adaptive_mesh_iterations'] = 0  # no adaptive mesh refinement
settings['boundary'] = ['ABC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']  # absorbing boundary condition
settings['margin'] = 50.0  # distance in microns from GDSII geometry boundary to stackup boundary
settings['air_around'] = 20.0  # air margin around SG13 stackup boundary up to simulation boundary, must not be 0

# ===================== port definitions =======================
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1.0, port_Z0=50.0, source_layernum=201, from_layername='Metal1', to_layername='TopMetal2', direction='Z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1.0, port_Z0=50.0, source_layernum=202, from_layername='Metal1', to_layername='TopMetal2', direction='Z'))

# ================= read stackup and geometries =================
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (settings['SubstrateFile'])
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# read geometries from GDSII
allpolygons = gds_reader.read_gds(settings['GdsFile'], 
	layernumbers,
	purposelist=settings['purpose'], 
	metals_list=metals_list, 
	preprocess=settings['preprocess_gds'], 
	merge_polygon_size=settings['merge_polygon_size'],
	gds_boundary_layers=dielectrics_list.get_boundary_layers(),
	mirror=False, 
	offset_x=0, offset_y=0,
	layernumber_offset=0)


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

# for convenience, write run script to model directory
utilities.create_run_script(settings['sim_path'])

# run after creating mesh and Palace config.json 
if start_simulation:
  try:
      os.chdir(sim_path)
      subprocess.run(run_command, shell=True)
  except:
      print(f'Unable to run Palace using command ',run_command)
