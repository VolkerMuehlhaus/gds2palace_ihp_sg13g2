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

# MODEL FOR GMSH WITH PALACE

import os
import sys
import subprocess

# we expect gds2palace in the same directory as this model file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))
from gds2palace import *
utilities.check_module_version("gds2palace", "0.1.0")

# Model comments
# First test model as basis for experiments with Elmer thermal


# ===================== input files and path settings =======================

gds_filename = "simplest_with_source.gds"   # geometries
XML_filename = "SG13_interposer_thermal_typicalvalues.xml"          # stackup
cellname = "HeatSpreader01B_M"

# preprocess GDSII for safe handling of cutouts/holes?
preprocess_gds = True

# merge via polygons with distance less than .. microns, set to 0 to disable via merging.
merge_polygon_size = 0.5

# get path for this simulation file
script_path = utilities.get_script_path(__file__)

# use script filename as model basename
model_basename = utilities.get_basename(__file__)

# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename, dirname='elmer_model')
print('Simulation data directory: ', sim_path)

# change path to models script path
modelDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(modelDir)

# ======================== simulation settings ================================

settings = {}

settings['unit']   = 1e-6  # geometry is in microns
settings['margin'] = 100    # distance in microns from GDSII geometry boundary to simulation boundary 

settings['refined_cellsize'] = 5  # only refines near sources for elmer_thermal

settings['meshsize_max'] = 100  # microns, override cells_per_wavelength 

settings['elmer_thermal'] = True # create all metals as volumes, enable Elmer output (not ready for thermal, manual edits required)

# settings['no_preview']=True  # swkip preview of outlines, show meshed metals only

# Thermal source and constant temperature boundary from GDSII Data, polygon geometry from specified special layer
thermal_objects = simulation_setup.all_thermal_objects()
thermal_objects.add_heatsource(simulation_setup.heatsource(power=0.65,source_layernum=201, target_layername='TFR'))
thermal_objects.add_consttemp(simulation_setup.constanttemp(temp=298,source_layernum=202, target_layername='BACKSIDEGND'))


# ======================== simulation ================================

# get technology stackup data
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)
# get list of layers from technology
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(thermal_objects.layers)

# read geometries from GDSII, only purpose 0
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, preprocess=preprocess_gds, merge_polygon_size=merge_polygon_size, cellname=cellname)


########### create model ###########

settings['thermal_objects'] = thermal_objects
settings['materials_list'] = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list'] = metals_list
settings['layernumbers'] = layernumbers
settings['allpolygons'] = allpolygons
settings['sim_path'] = sim_path
settings['model_basename'] = model_basename


config_name, data_dir = simulation_setup.create_elmer_thermal (settings)

