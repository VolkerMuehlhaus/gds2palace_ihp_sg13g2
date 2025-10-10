# MODEL FOR GMSH WITH PALACE

import os
import sys
import subprocess

# we expect gds2palace in the same directory as this model file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))
from gds2palace import *

# Model comments
# 
# Microstrip TM2 over Metal1 with coded geometry (no GDSII)


# ======================== workflow settings ================================

# preview model/mesh only, without running solver?
start_simulation = False
run_command = ['./run_sim']   

# ===================== input files and path settings =======================

wline = 15
lline = 880
gnd_oversize = 100

mesh  = 2  # define here, so that we can add this information to output filenames
order = 2  # define here, so that we can add this information to output filenames


XML_filename = "SG13G2_nosub.xml"          # stackup

# preprocess GDSII for safe handling of cutouts/holes?
preprocess_gds = False

# merge via polygons with distance less than .. microns, set to 0 to disable via merging.
merge_polygon_size = 0

# get path for this simulation file
script_path = utilities.get_script_path(__file__)

# use script filename as model basename, with parameters for suffix
model_basename = utilities.get_basename(__file__) + '_w' + str(wline) + '_l' + str(lline) + '_mesh' + str(mesh) + '_order' + str(order)

# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename)
print('Simulation data directory: ', sim_path)

# change path to models script path
modelDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(modelDir)

# ======================== simulation settings ================================

settings = {}

settings['unit']   = 1e-6  # geometry is in microns
settings['margin'] = 50    # distance in microns from GDSII geometry boundary to simulation boundary 

settings['fstart']  = 0e9
settings['fstop']   = 100e9
settings['fstep']   = 2.5e9

settings['refined_cellsize'] = mesh  # mesh cell size in conductor region
settings['cells_per_wavelength'] = 10   # how many mesh cells per wavelength, must be 10 or more

settings['meshsize_max'] = 70  # microns, override cells_per_wavelength 
settings['adaptive_mesh_iterations'] = 0
settings['z_thickness_factor'] = 0.33  

settings['nogui'] = ('nogui' in sys.argv)  # check if nogui specified on command line, then create files without showing 3D model

# Ports from GDSII Data, polygon geometry from specified special layer
# Excitations can be switched off by voltage=0, those S-parameter will be incomplete then

simulation_ports = simulation_setup.all_simulation_ports()
# instead of in-plane port specified with target_layername, we here use via port specified with from_layername and to_layername
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, from_layername='Metal1', to_layername='TopMetal2', direction='z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, from_layername='Metal1', to_layername='TopMetal2', direction='z'))


# ======================== simulation ================================

# get technology stackup data
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)
# get list of layers from technology
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)



# Here, we do NOT load a GDSII file, and create an empty all_polygons_list() instead
# allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, preprocess=preprocess_gds)
allpolygons = gds_reader.all_polygons_list()

# Add rectangles manually
# microstrip line
allpolygons.add_rectangle(x1=0, y1=-wline/2, x2=lline, y2=wline/2, layernum=metals_list.getbylayername('TopMetal2').layernum)
# port rectangles, mapped to via ports defined above by their layer number. Parameter is_port=True leads to mesh refinement for this polygon.
allpolygons.add_rectangle(x1=0,  y1=-wline/2, x2=0,   y2=wline/2, layernum=201, is_port=True)
allpolygons.add_rectangle(x1=lline, y1=-wline/2, x2=lline, y2=wline/2, layernum=202, is_port=True)
# ground plane on Metal1 
allpolygons.add_rectangle(x1=-gnd_oversize,  y1=-wline/2-gnd_oversize, x2=lline+gnd_oversize, y2=wline/2+gnd_oversize, layernum=metals_list.getbylayername('Metal1').layernum)



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
