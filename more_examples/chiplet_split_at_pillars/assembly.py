# Reference model: die and interposer in one model, joined by copper pillars.
# A GSG line on the interposer, through two signal pillars into a 300 um line on the die and back.
# Four in-plane probe ports on the interposer, two at each end (signal to the ground pad above and below).
#
# Layouts: run prepare_layouts.py first. See README.md.

import os
from gds2palace import *

# ---------- input files ----------
die_filename = "die_forEM.gds"
interposer_filename = "interposer_forEM.gds"
XML_filename = "assembly.xml"

# the interposer is mounted upside down on the die (flip-chip)
mirror = True               # mirror the interposer layout about the y axis
offset_x = 780              # then shift it, so that its pillar pads lie on the die's pillars
offset_y = 0
layernumber_offset = 1000   # interposer layers become 1000 + layer, as in the stackup

script_path = utilities.get_script_path(__file__)
model_basename = utilities.get_basename(__file__)
sim_path = utilities.create_sim_path(script_path, model_basename)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------- settings ----------
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
# probe ports on the interposer's TopMetal2, drawn on 201-204 in the interposer layout
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, target_layername='iTopMetal2', direction='y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, target_layername='iTopMetal2', direction='-y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=3, voltage=1, port_Z0=50, source_layernum=203, target_layername='iTopMetal2', direction='y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=4, voltage=1, port_Z0=50, source_layernum=204, target_layername='iTopMetal2', direction='-y'))
simulation_ports.apply_layernumber_offset(layernumber_offset)    # the port layers are read with the interposer

# ---------- read stackup and layouts ----------
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

# die: drawing (0), copper pillars (41/35), outline (39/4)
allpolygons = gds_reader.read_gds(die_filename, layernumbers, purposelist=[0, 35, 4],
                                  metals_list=metals_list,
                                  gds_boundary_layers=dielectrics_list.get_boundary_layers())
# interposer: drawing (0) and outline (39/4), flipped
interposer_polygons = gds_reader.read_gds(interposer_filename, layernumbers, purposelist=[0, 4],
                                          metals_list=metals_list,
                                          gds_boundary_layers=dielectrics_list.get_boundary_layers(),
                                          mirror=mirror, offset_x=offset_x, offset_y=offset_y,
                                          layernumber_offset=layernumber_offset)
allpolygons.merge(interposer_polygons)

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
