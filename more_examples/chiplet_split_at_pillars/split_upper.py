# Split model, upper part: the interposer, down to the PEC cut plane at half pillar height.
# Ports 1-4 are the probe ports of assembly.py. Ports 5 and 6 are tube ports on the signal pillars, from the cut
# plane up to the interposer's TopMetal2, on the same squares as in split_lower.py.
#
# Layouts: run prepare_layouts.py first. Join the result with split_lower with join_split.py. See README.md.

import os
from gds2palace import *

# ---------- input files ----------
interposer_filename = "interposer_forEM.gds"
split_filename = "split_shapes.gds"     # cut plane, ground pillars, tube ports (die coordinates)
XML_filename = "split_upper.xml"

# the interposer is mounted upside down (flip-chip), placed as in assembly.py
mirror = True
offset_x = 780
offset_y = 0
layernumber_offset = 1000

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
simulation_ports = simulation_setup.all_simulation_ports()
# probe ports as in assembly.py, read with the interposer layout: layer number + 1000
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=1, voltage=1, port_Z0=50, source_layernum=201, target_layername='iTopMetal2', direction='y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=2, voltage=1, port_Z0=50, source_layernum=202, target_layername='iTopMetal2', direction='-y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=3, voltage=1, port_Z0=50, source_layernum=203, target_layername='iTopMetal2', direction='y'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=4, voltage=1, port_Z0=50, source_layernum=204, target_layername='iTopMetal2', direction='-y'))
simulation_ports.apply_layernumber_offset(layernumber_offset)
# tube ports, read from split_shapes.gds without offset: added after apply_layernumber_offset()
# direction '-z': the same polarity as in split_lower.py, where the port runs upwards to the cut plane
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=5, voltage=1, port_Z0=50, source_layernum=205, from_layername='CUT', to_layername='iTopMetal2', direction='-z'))
simulation_ports.add_port(simulation_setup.simulation_port(portnumber=6, voltage=1, port_Z0=50, source_layernum=206, from_layername='CUT', to_layername='iTopMetal2', direction='-z'))

# ---------- read stackup and layouts ----------
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)

allpolygons = gds_reader.read_gds(interposer_filename, layernumbers, purposelist=[0, 4],
                                  metals_list=metals_list,
                                  gds_boundary_layers=dielectrics_list.get_boundary_layers(),
                                  mirror=mirror, offset_x=offset_x, offset_y=offset_y,
                                  layernumber_offset=layernumber_offset)
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
