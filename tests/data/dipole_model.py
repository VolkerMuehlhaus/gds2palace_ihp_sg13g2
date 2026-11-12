# Model script of the dipole fixture (tests/test_examples_geometry.py): a slot antenna as exported by KLayout,
# with one via port from TopMetal2 to the Metal1 ground plane. Coarse mesh: this is a test of the geometry.
import os

from gds2palace import *

gds_filename = "dipole_port_sg13_forPalace_em.gds"
XML_filename = utilities.get_stackup_path("SG13G2_FEM_200um.xml")

script_path = utilities.get_script_path(__file__)
model_basename = utilities.get_basename(__file__)
sim_path = utilities.create_sim_path(script_path, model_basename)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

settings = {}
settings['unit'] = 1e-6
settings['margin'] = 100
settings['fstart'] = 100e9
settings['fstop'] = 140e9
settings['fstep'] = 10e9
settings['refined_cellsize'] = 20
settings['cells_per_wavelength'] = 10
settings['meshsize_max'] = 200
settings['order'] = 1
settings['no_gui'] = True

simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(
    portnumber=1, voltage=1, port_Z0=50, source_layernum=201,
    from_layername='TopMetal2', to_layername='Metal1', direction='z'))

materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list,
                                  merge_polygon_size=0,
                                  gds_boundary_layers=dielectrics_list.get_boundary_layers(), cellname="t1")

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
