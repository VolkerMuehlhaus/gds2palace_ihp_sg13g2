"""Via port shapes: a line gives one vertical port sheet, a shape with area gives a tube (the four side walls
of its bounding box as one multielement port). Tube ports are not de-embedded by combine_snp.

    python -m pytest tests/test_tube_port.py
"""
import json
import os
import sys

import numpy as np
import pytest

from gds2palace import simulation_setup, stackup_reader, utilities
from gds2palace.util_gds_reader import all_polygons_list

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import combine_extend_snp as ce  # noqa: E402
import skrf as rf  # noqa: E402

STACKUP = utilities.get_stackup_path('SG13G2_FEM_200um.xml')
TM2, M1 = 134, 8


@pytest.mark.parametrize('size_x, size_y, tube', [
    (0, 20, False),         # a line
    (0.005, 20, False),     # a line drawn as a path of minimum width
    (1, 499, False),        # a long, narrow box is still a line
    (2, 20, False),         # exactly 10 %: a line
    (2.1, 20, True),
    (20, 20, True),
    (20, 8, True),
    (0, 0, False),          # a point
])
def test_shape_decides_between_sheet_and_tube(size_x, size_y, tube):
    assert simulation_setup.via_port_is_tube(size_x, size_y) is tube


def build(tmp_path, port_shapes):
    """a TopMetal2 line over a Metal1 plane with a via port (Metal1 -> TopMetal2) at each end"""
    materials, dielectrics, metals = stackup_reader.read_substrate(STACKUP)
    ap = all_polygons_list()
    ap.add_rectangle(0, -10, 200, 10, TM2)
    ap.add_rectangle(-20, -40, 220, 40, M1)
    for k, shape in enumerate(port_shapes):
        ap.add_rectangle(*shape, 201 + k)
    ports = simulation_setup.all_simulation_ports()
    for n in (1, 2):
        ports.add_port(simulation_setup.simulation_port(portnumber=n, voltage=1, port_Z0=50, source_layernum=200 + n,
                                                        from_layername='Metal1', to_layername='TopMetal2', direction='z'))
    sim_path = utilities.create_sim_path(str(tmp_path), 'line', dirname='palace_model')
    settings = dict(unit=1e-6, margin=50, air_around=50, fstart=0, fstop=50e9, fstep=10e9,
                    refined_cellsize=5, meshsize_max=70, order=1, no_gui=True, no_preview=True,
                    simulation_ports=ports, materials_list=materials, dielectrics_list=dielectrics, metals_list=metals,
                    allpolygons=ap, sim_path=sim_path, model_basename='line')
    simulation_setup.create_palace(ports.all_active_excitations(), settings)
    config = json.load(open(os.path.join(sim_path, 'config.json')))
    info = json.load(open(os.path.join(sim_path, 'port_information.json')))
    return {p['Index']: p for p in config['Boundaries']['LumpedPort']}, info['ports']


def test_box_gives_a_tube_and_line_gives_a_sheet(tmp_path):
    """port 1 drawn as a 16 x 16 box, port 2 as a line across the line end"""
    lumped, info = build(tmp_path, [(2, -8, 18, 8), (198, -8, 198, 8)])

    # port 1: four elements, all with the port's direction; Palace keeps the port impedance R for the whole port
    assert lumped[1]['R'] == 50 and 'Attributes' not in lumped[1]
    assert [e['Direction'] for e in lumped[1]['Elements']] == ['Z'] * 4
    assert len({e['Attributes'][0] for e in lumped[1]['Elements']}) == 4
    walls = [p for p in info if p['portnumber'] == 1]
    assert [p['element'] for p in walls] == [1, 2, 3, 4] and all(p['tube'] for p in walls)
    # the walls are the four sides of the drawn box, each as wide as its side
    assert {(p['xmin'], p['xmax'], p['ymin'], p['ymax']) for p in walls} == \
        {(2, 2, -8, 8), (18, 18, -8, 8), (2, 18, -8, -8), (2, 18, 8, 8)}
    assert all(p['width'] == 16 for p in walls)
    assert len({(p['zmin'], p['zmax'], p['length']) for p in walls}) == 1 and walls[0]['length'] > 0

    # port 2: one sheet as before, no tube mark
    assert lumped[2]['Direction'] == 'Z' and len(lumped[2]['Attributes']) == 1
    sheet = [p for p in info if p['portnumber'] == 2]
    assert len(sheet) == 1 and 'tube' not in sheet[0] and sheet[0]['width'] == 16


def test_tube_port_is_not_deembedded(tmp_path, capsys):
    """combine_snp removes the estimated port inductance of sheet ports only: a tube port stands for a conductor"""
    f = rf.Frequency(1, 50, 6, unit='GHz')
    s = np.zeros((6, 2, 2), dtype=complex)
    s[:, 0, 1] = s[:, 1, 0] = 1                   # an ideal thru
    name = str(tmp_path / 'thru.s2p')
    rf.Network(frequency=f, s=s, z0=50).write_touchstone(name)
    wall = dict(Z0=50, direction='Z', length=10.0, width=16.0)
    info = {'unit': 1e-6, 'ports': [dict(wall, portnumber=1, element=k, tube=True) for k in (1, 2, 3, 4)] +
            [dict(wall, portnumber=2, element=1)]}
    ce.port_deembedding(name, True, info)
    out = capsys.readouterr().out
    assert 'Port 1 is a tube port' in out and 'at port 2' in out and 'at port 1' not in out

    # only the negative L of port 2 is in the result: the same as de-embedding port 2 alone
    result = rf.Network(str(tmp_path / 'thru_deembedded.s2p'))
    ce.port_deembedding(name, True, {'unit': 1e-6, 'ports': [dict(wall, portnumber=2, element=1)]})
    only_port2 = rf.Network(str(tmp_path / 'thru_deembedded.s2p'))
    assert np.allclose(result.s, only_port2.s) and abs(result.s[-1, 0, 0]) > 1e-4
