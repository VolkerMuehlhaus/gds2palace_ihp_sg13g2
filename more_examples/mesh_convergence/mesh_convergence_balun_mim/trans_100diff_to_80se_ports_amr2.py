# Model for IHP OpenPDK EM workflow created using setupEM
#
# trans_100diff_to_80se_ports_amr2: adaptive mesh refinement, starting mesh
# refined_cellsize=2um, 2 AMR iterations.
# See trans_100diff_to_80se_ports.py (the baseline) for full documentation of
# the port setup, true external impedances, and layer assignment.
import os, sys, subprocess

from gds2palace import *

# get path for this simulation file
script_path = utilities.get_script_path(__file__)
# use script filename as model basename
model_basename = utilities.get_basename(__file__)
# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename)

# ========================= workflow settings ==========================

# ===================== input files and settings =======================
settings={}
settings['GdsFile'] = 'trans_100diff_to_80se_ports.gds'
settings['SubstrateFile'] = 'SG13G2_200um.xml'
settings['preprocess_gds'] = True
settings['merge_polygon_size'] = 3.0  # merges each TopVia2 array into one polygon (via pitch ~1.1um, closest inter-array gap ~15um)
settings['purpose'] = [0]
settings['fstart'] = 17.0e9
settings['fstop'] = 22.0e9
settings['fstep'] = 0.1e9
settings['refined_cellsize'] = 2.0  # AMR starting mesh
settings['refined_cellsize_override'] = [['Metal3', 5.0]]  # Metal3 kept fixed at 5um regardless of the mesh sweep
settings['order'] = 2
settings['cells_per_wavelength'] = 10.0
settings['meshsize_max'] = 100.0
settings['adaptive_mesh_iterations'] = 2
settings['boundary'] = ['ABC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']
settings['margin'] = 100.0
settings['air_around'] = 20.0
settings['no_gui'] = ('nogui' in sys.argv)  # check if nogui specified on command line, then create files without showing 3D model

# ===================== port definitions =======================
# port_Z0=50.0 on every port for the EM simulation itself -- see the baseline
# script's docstring regarding the true 80/100 ohm external impedances.
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1.0, port_Z0=50.0, source_layernum=201, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))  # single-ended (target 80 ohm)
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1.0, port_Z0=50.0, source_layernum=202, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))  # differential + (target 100 ohm diff)
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=3, voltage=1.0, port_Z0=50.0, source_layernum=203, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))  # differential - (target 100 ohm diff)

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
