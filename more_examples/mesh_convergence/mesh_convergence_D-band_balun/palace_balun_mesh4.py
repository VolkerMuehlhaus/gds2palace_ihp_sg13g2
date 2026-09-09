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
settings['unit'] = 1e-06
settings['purpose'] = [0]
settings['GdsFile'] = 'Balun_140-170G_RupokDas_with_ports.gds'
settings['SubstrateFile'] = 'SG13G2_nosub.xml'
settings['preprocess_gds'] = True
settings['merge_polygon_size'] = 1.0
settings['margin'] = 50.0
settings['fstart'] = 100.0e9
settings['fstop'] = 200.0e9
settings['fstep'] = 1.0e9
settings['refined_cellsize'] = 4.0
settings['cells_per_wavelength'] = 10.0
settings['meshsize_max'] = 70.0
settings['adaptive_mesh_iterations'] = 0
settings['cellname'] = ''
settings['variable_overrides'] = {}
settings['refined_cellsize_override'] = [['Metal3', 5.0]]
settings['order'] = 2
settings['boundary'] = ['ABC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']
settings['air_around'] = 50.0
settings['no_gui'] = True

# ===================== port definitions =======================
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1.0, port_Z0=50.0, source_layernum=201, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1.0, port_Z0=50.0, source_layernum=202, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=3, voltage=1.0, port_Z0=50.0, source_layernum=203, from_layername='Metal3', to_layername='TopMetal2', direction='Z'))

# ================= read stackup and geometries =================
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (settings['SubstrateFile'], variable_overrides=settings['variable_overrides'])
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# read geometries from GDSII
allpolygons = gds_reader.read_gds(settings['GdsFile'],
	layernumbers,
	cellname=settings['cellname'],
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
      if sys.platform.startswith('linux'):
          os.chmod('run_sim', 0o755)
      subprocess.run(run_command, shell=True)
  except:
      print(f'Unable to run Palace using command ',run_command)
