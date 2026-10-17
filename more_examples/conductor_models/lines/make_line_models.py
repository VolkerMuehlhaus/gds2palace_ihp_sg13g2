"""Palace models of a straight TopMetal2 microstrip over an ideal ground, for the conductor model study.

Line: TopMetal2 strip of width w along x, length L. Two lengths per width (100 and 300 um), so that the port transitions
cancel in the two-length extraction (analyze_lines.py). Ground: SUBGND plate (PEC sheet, 11.23 um below TopMetal2),
300 um wide, under the whole line, so that only the TopMetal2 strip has conductor loss. Ports: lumped ports from SUBGND
to TopMetal2 at both line ends (0.1 um port boxes). Stackup: SG13G2_FEM_200um_passi3D.xml (conformal passivation, all
dielectrics lossless). Solved at fixed frequencies, without the adaptive sweep, whose tolerance would mask the small
line loss. The skin layers of 'solve_inside_skin' are sized for the highest of these frequencies (150 GHz).

Models (conductor model, refined_cellsize):
  surface_mesh2            'surface', 2 um
  solve_inside_mesh2       'solve_inside', 2 um
  solve_inside_skin_mesh2  'solve_inside_skin', 2 um
  solve_inside_skin_mesh5  'solve_inside_skin', 5 um (widths of 10 and 20 um only: the cell must not exceed the trace)

Reference data in reference/ (from the gds2palace filled_vs_surface study): filled metals at refined_cellsize 0.25 um
(converged, *_fill025) and the same lines with ideal conductors (*_pec2), which give the losses outside the conductor.
Run in the palace venv:  python make_line_models.py      (writes gds/ and palace_model/)
"""
import os
import sys
import json

import gdspy
from gds2palace import simulation_setup, stackup_reader, gds_reader, utilities

HERE = os.path.dirname(os.path.abspath(__file__))
STACKUP = os.path.join(HERE, 'SG13G2_FEM_200um_passi3D.xml')
WIDTHS = (2.01, 4.5, 10, 20)
LENGTHS = (100, 300)
MODELS = {'surface_mesh2': ('surface', 2.0), 'solve_inside_mesh2': ('solve_inside', 2.0),
          'solve_inside_skin_mesh2': ('solve_inside_skin', 2.0), 'solve_inside_skin_mesh5': ('solve_inside_skin', 5.0)}
FREQS_GHZ = [0.01, 1, 5, 10, 20, 30, 50, 75, 100, 150]
GROUND_WIDTH = 300
PORT_DELTA = 0.1


def name_of(w, L, model):
    return f'line_w{w}_L{L}_{model}'.replace('.', 'p')


def runs():
    """(w, L, model) of all runs of this study"""
    return [(w, L, m) for w in WIDTHS for m in MODELS for L in LENGTHS
            if not (m == 'solve_inside_skin_mesh5' and w < MODELS[m][1])]


def make_gds(w, L, filename):
    lib = gdspy.GdsLibrary()
    c = gdspy.Cell('line', exclude_from_current=True)     # not registered globally: several layouts per process
    lib.add(c)
    c.add(gdspy.Rectangle((0, -w / 2), (L, w / 2), layer=134))                             # TopMetal2 strip
    c.add(gdspy.Rectangle((0, -w / 2), (PORT_DELTA, w / 2), layer=201))                   # port 1 box
    c.add(gdspy.Rectangle((L - PORT_DELTA, -w / 2), (L, w / 2), layer=202))               # port 2 box
    c.add(gdspy.Rectangle((-20, -GROUND_WIDTH / 2), (L + 20, GROUND_WIDTH / 2), layer=250))  # SUBGND plate (PEC)
    lib.write_gds(filename)


def create_model(w, L, model):
    conductor_model, cellsize = MODELS[model]
    name = name_of(w, L, model)
    gds = os.path.join(HERE, 'gds', f"line_w{str(w).replace('.', 'p')}_L{L}.gds")
    os.makedirs(os.path.dirname(gds), exist_ok=True)
    make_gds(w, L, gds)
    settings = dict(unit=1e-6, margin=100, air_around=50, boundary=['ABC'] * 6, fstart=0, fstop=150e9, fstep=0.25e9,
                    refined_cellsize=cellsize, cells_per_wavelength=10, meshsize_max=70, order=2,
                    adaptive_mesh_iterations=0, no_gui=True, no_preview=True, conductor_model=conductor_model)
    ports = simulation_setup.all_simulation_ports()
    for k in (1, 2):
        ports.add_port(simulation_setup.simulation_port(portnumber=k, voltage=1, port_Z0=50, source_layernum=200 + k,
                                                        from_layername='SUBGND', to_layername='TopMetal2', direction='z'))
    materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(STACKUP)
    layernumbers = metals_list.getlayernumbers()
    layernumbers.extend(ports.portlayers)
    allpolygons = gds_reader.read_gds(gds, layernumbers, purposelist=[0], metals_list=metals_list, preprocess=True,
                                      merge_polygon_size=0, gds_boundary_layers=dielectrics_list.get_boundary_layers())
    settings.update(simulation_ports=ports, materials_list=materials_list, dielectrics_list=dielectrics_list,
                    metals_list=metals_list, layernumbers=layernumbers, allpolygons=allpolygons,
                    sim_path=utilities.create_sim_path(HERE, name, dirname='palace_model'), model_basename=name)
    simulation_setup.create_palace(ports.all_active_excitations(), settings)
    # fixed frequencies, no adaptive sweep
    cfg = os.path.join(HERE, 'palace_model', name + '_data', 'config.json')
    c = json.load(open(cfg))
    c['Solver']['Driven']['Samples'] = [{'Type': 'Point', 'Freq': FREQS_GHZ, 'SaveStep': 0}]
    c['Solver']['Driven']['AdaptiveTol'] = 0.0
    json.dump(c, open(cfg, 'w'), indent=4)
    return name


if __name__ == '__main__':
    os.chdir(HERE)
    for w, L, m in runs():
        name = name_of(w, L, m)
        if os.path.exists(os.path.join(HERE, 'palace_model', name + '_data', 'config.json')):
            continue
        print('building', name, flush=True)
        create_model(w, L, m)
    print(len(runs()), 'models')
