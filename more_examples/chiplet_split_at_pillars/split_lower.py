# Split model, lower part: the die, up to a PEC cut plane at half pillar height.
# The ground pillars are copper up to the cut plane. Each signal pillar is replaced by a tube port from the die's
# TopMetal2 to the cut plane: one 29 um square per pillar on GDS 205/206 in split_shapes.gds, which gds2palace turns
# into the four side walls of the square (gds2palace 0.12.0 and newer).
#
# Layouts: run prepare_layouts.py first. Join the result with split_upper with join_split.py. See README.md.

import os
from gds2palace import *

# ---------- input files ----------
die_filename = "die_forEM.gds"
split_filename = "split_shapes.gds"     # cut plane, ground pillars, tube ports (die coordinates)
XML_filename = "split_lower.xml"

script_path = utilities.get_script_path(__file__)
model_basename = utilities.get_basename(__file__)
sim_path = utilities.create_sim_path(script_path, model_basename)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------- settings: the same as in assembly.py ----------
settings = {}
settings['unit'] = 1e-6
settings['margin'] = 20
settings['air_around'] = 50
settings['fstart'] = 0
settings['fstop'] = 100e9
settings['fstep'] = 2e9
settings['refined_cellsize'] = 5
settings['cells_per_wavelength'] = 10
settings['meshsize_max'] = 50
settings['order'] = 2
settings['no_gui'] = True

# ---------- ports ----------
# tube ports on the signal pillars, from the die's TopMetal2 up to the cut plane
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=205, from_layername='TopMetal2', to_layername='CUT', direction='z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=206, from_layername='TopMetal2', to_layername='CUT', direction='z'))

# ---------- read stackup and layouts ----------
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# die: drawing (0) and outline (39/4); not the pillars (41/35), they come from split_shapes.gds
allpolygons = gds_reader.read_gds(die_filename, layernumbers, purposelist=[0, 4],
                                  metals_list=metals_list,
                                  gds_boundary_layers=dielectrics_list.get_boundary_layers())
split_polygons = gds_reader.read_gds(split_filename, layernumbers, purposelist=[0], metals_list=metals_list)
allpolygons.merge(split_polygons)

# ---------- create the model ----------
settings['simulation_ports'] = simulation_ports
settings['materials_list'] = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list'] = metals_list
settings['layernumbers'] = layernumbers
settings['allpolygons'] = allpolygons
settings['sim_path'] = sim_path
settings['model_basename'] = model_basename

excite_ports = simulation_ports.all_active_excitations()
config_name, data_dir = simulation_setup.create_palace(excite_ports, settings)
utilities.create_run_script(sim_path)
