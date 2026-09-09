# Model for IHP OpenPDK EM workflow created using setupEM
#
# verify_MIM_nominal_280: single-port EM extraction of the nominal-280fF MIM
# capacitor used in trans_100diff_to_80se_ports.gds, to check the simulated
# capacitance against the GDS text label's nominal value.
#
# Port 1 (layer 201) is a lumped via port straddling the capacitor directly:
# from_layername='Metal3' (bottom plate net) to to_layername='TopMetal2' (top
# plate net, reached through the Vmim/TopVia2 stack) -- confirmed by direct
# geometric overlap check against the GDS, same convention as the ports in
# trans_100diff_to_80se_ports.py. A single-point 1 GHz evaluation is used
# (settings['fpoint']) since this is a capacitance check, not a sweep.
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
settings['GdsFile'] = 'verify_MIM_nominal_280.gds'
settings['SubstrateFile'] = 'SG13G2_200um.xml'
settings['preprocess_gds'] = True
settings['merge_polygon_size'] = 3.0  # same as trans_100diff_to_80se_ports.py, merges each TopVia2/Vmim array
settings['purpose'] = [0]
settings['fpoint'] = [1.0e9, 0.1e9]  # capacitance check at 1 GHz and 0.1 GHz, no sweep needed
settings['refined_cellsize'] = 1.0  # halved from 2.0, to check mesh sensitivity of the +8% discrepancy
settings['order'] = 2
settings['cells_per_wavelength'] = 10.0
settings['meshsize_max'] = 100.0
settings['adaptive_mesh_iterations'] = 0
settings['boundary'] = ['ABC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']
settings['margin'] = 100.0
settings['air_around'] = 20.0
settings['no_gui'] = ('nogui' in sys.argv)  # check if nogui specified on command line, then create files without showing 3D model

# ===================== port definitions =======================
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1.0, port_Z0=50.0, source_layernum=201, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))

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
