########################################################################
#
# Copyright 2025-2026 Volker Muehlhaus and IHP PDK Authors
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

import os
import sys
import subprocess

# we expect gds2palace in the same directory as this model file
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))
from gds2palace import *

# Model comments
#
# Demonstrates a stackup with TEMPERATURE-DEPENDENT metal conductivity: Metal1-Metal5,
# TopMetal1 and TopMetal2 all use the standard sheet-resistance temperature-coefficient
# equation R(T) = R(T0) * [1 + TC1*(T-T0)] (so Conductivity = 1/R becomes a function of
# temperature), with Temp_Celsius declared as a <Variable> in SG13G2_100um_tcoef.xml -
# see that file's comments and README.md for the exact expressions and where the TC1
# values come from.
#
# The model itself is the STANDARD line_simple_viaport test structure (same GDS as
# ../../workflow/line_simple_viaport.py / palace_line_viaport.py): a single straight
# trace on TopMetal2 over a solid Metal1 ground plane, with a via port at each end
# (Metal1 -> TopMetal2). An earlier version of this example instead used 7 narrow
# (2 um wide) lines directly on Metal1..TopMetal2 referenced to an artificial ground
# plane - that hit a known Palace limitation: its thin-metal surface-impedance
# boundary condition is a skin-effect/high-frequency approximation, and for a trace
# whose width is only on the order of its own thickness, the side-wall contribution
# it can't resolve becomes a large fraction of the cross-section, giving an inaccurate
# DC/low-frequency resistance (this is not an issue in the skin-effect regime at high
# frequency, or for a normally-proportioned trace like this one, ~15 um wide vs.
# TopMetal2's 3 um thickness).
#
# Temperature range: the TC1 coefficients are only valid from -40 degC to 125 degC
# per the IHP process specification. This script builds the model at both room
# temperature (Temp_Celsius = 26.85 degC = 300 K, the sigma0 reference point) and at
# 125 degC (the top of the valid range), each into its own output directory, so the
# two can be compared directly.


# ======================== workflow settings ================================

# temperatures to build a model for, degC - room temperature (= the stackup's own
# sigma0 reference point) and 125 degC, the top of the TC1 data's valid range
temperatures_C = [26.85, 125.0]

#start solver after creating the model?
start_simulation = False
run_command = ['./run_sim']

# ===================== input files and path settings =======================

gds_filename = "line_simple_viaport.gds"   # geometries - standard line_simple_viaport test structure
XML_filename = "SG13G2_100um_tcoef.xml"    # stackup

# merge via polygons with distance less than .. microns, set to 0 to disable via merging.
merge_polygon_size = 0

# get path for this simulation file
script_path = utilities.get_script_path(__file__)

# change path to models script path
modelDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(modelDir)

for Temp_Celsius in temperatures_C:

    # gmsh/create_palace() leaves the working directory changed after building a
    # model (observed on Windows) - reset it every iteration so the relative
    # gds_filename/XML_filename below still resolve on the 2nd+ temperature
    os.chdir(modelDir)

    # use script filename as model basename - include Temp_Celsius so the two
    # temperature runs each get their own output directory instead of overwriting
    # one another
    model_basename = utilities.get_basename(__file__) + f'_T{Temp_Celsius}C'

    # set and create directory for simulation output
    sim_path = utilities.create_sim_path (script_path,model_basename)
    print('Simulation data directory: ', sim_path)

    # ======================== simulation settings ================================

    settings = {}

    settings['unit']   = 1e-6  # geometry is in microns
    settings['margin'] = 50    # distance in microns from GDSII geometry boundary to simulation boundary

    settings['fstart']  = 0e9
    settings['fstop']   = 100e9
    settings['fstep']   = 2.5e9

    settings['refined_cellsize'] = 2  # mesh cell size in conductor region
    settings['cells_per_wavelength'] = 10   # how many mesh cells per wavelength, must be 10 or more

    settings['meshsize_max'] = 70  # microns, override cells_per_wavelength
    settings['adaptive_mesh_iterations'] = 0

    settings['no_gui'] = True # batch run without showing model in gmsh

    # get technology stackup data - Temp_Celsius overrides the XML's own default
    # (26.85 degC = 300 K) here
    variable_overrides = {'Temp_Celsius': Temp_Celsius}


    # this stackup keeps the full lossy Silicon substrate (unlike the reduced
    # SG13G2_nosub.xml the standalone line_simple_viaport example normally uses,
    # which can get away with plain PEC boundaries) - use absorbing boundaries here
    settings['boundary'] = ['ABC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']

    # Ports from GDSII Data, polygon geometry from specified special layer - same
    # via-port definition as the standard line_simple_viaport example: Metal1 is the
    # real, physically-modeled ground plane, TopMetal2 carries the signal trace
    simulation_ports = simulation_setup.all_simulation_ports()
    simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, from_layername='Metal1', to_layername='TopMetal2', direction='z'))
    simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, from_layername='Metal1', to_layername='TopMetal2', direction='z'))

    # ======================== simulation ================================

    materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename, variable_overrides=variable_overrides)
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

    # for convenience, write run script to model directory
    utilities.create_run_script(sim_path)


    if start_simulation:
        try:
            os.chdir(sim_path)
            subprocess.run(run_command, shell=True)
        except:
            print(f"Unable to run Palace using command ",run_command)
