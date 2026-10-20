# D-band balun, conformal / single-frequency AMR study (see README.md in this folder)
# Model settings as in ../palace_balun_amr5.py; AMR settings are patched into config.json by amr_patch.py
import os, sys, subprocess

from gds2palace import *

# get path for this simulation file
script_path = utilities.get_script_path(__file__)
# use script filename as model basename
model_basename = utilities.get_basename(__file__)
# set and create directory for simulation output
sim_path = utilities.create_sim_path (script_path,model_basename)

sys.path.insert(0, script_path)
from amr_patch import patch_config

# ========================= study variant ==========================
# Stage 1: conformal AMR at 150 GHz, UpdateFraction 0.5, stopped after 2 passes (saves the 1.28M mesh of pass 3)
refined_cellsize = 5.0      # um, initial mesh
amr_max_its = 2            # AMR passes (0 = no AMR)
amr_conformal = True      # True: conformal refinement, False: Palace default (nonconformal, hanging nodes)
amr_update_fraction = 0.5   # Palace UpdateFraction: refine the elements that carry this fraction of the error
amr_max_size = 2e6          # Palace MaxSize: no further refinement once the mesh has more unknowns
amr_single_freq_GHz = 150.0   # AMR at this frequency only (None: full 100-200 GHz sweep in every pass)
amr_save_mesh = True      # save the final mesh, for the full sweep in stage 2 (make_stage2.py)

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
settings['GdsFile'] = os.path.join(script_path, '..', 'Balun_140-170G_RupokDas_with_ports.gds')
settings['SubstrateFile'] = os.path.join(script_path, '..', 'SG13G2_nosub.xml')
settings['preprocess_gds'] = True
settings['merge_polygon_size'] = 1.0
settings['margin'] = 50.0
# the mesh is always built for the full sweep (cells_per_wavelength at 200 GHz), also for single-frequency AMR
settings['fstart'] = 100.0e9
settings['fstop'] = 200.0e9
settings['fstep'] = 1.0e9
settings['refined_cellsize'] = refined_cellsize
settings['cells_per_wavelength'] = 10.0
settings['meshsize_max'] = 70.0
settings['adaptive_mesh_iterations'] = amr_max_its
settings['adaptive_mesh_conformal'] = amr_conformal
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

# AMR settings that gds2palace doesn't offer (UpdateFraction, single-frequency AMR)
if amr_max_its > 0:
    patch_config(config_name, update_fraction=amr_update_fraction, conformal=amr_conformal, max_its=amr_max_its,
                 max_size=amr_max_size, save_mesh=amr_save_mesh, single_freq_GHz=amr_single_freq_GHz)

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
