"""Port walls in gds2palace (util_calibration.py): finding the wall ports, the gap, D, the length of the standards, the
errors and warnings, the standards' geometry, and the model files. Layouts are built in memory; the last test meshes a
small line with gmsh (no Palace).

    python -m pytest tests/test_port_walls.py
"""
import json
import os

import pytest

from gds2palace import calibration, simulation_setup, stackup_reader, utilities
from gds2palace.util_gds_reader import all_polygons_list

STACKUP = utilities.get_stackup_path('SG13G2_FEM_200um.xml')
TM2, TM1, TV2, M1, SUBGND = 134, 126, 133, 8, 250
GSSG_LINES = [(-15, -5), (5, 15)]
GSSG_GROUNDS = [(-65, -25), (25, 65)]
BOUNDARY = ['PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']


@pytest.fixture(scope='module')
def stack():
    return stackup_reader.read_substrate(STACKUP)


def ports_for(numbers, voltage=1, target='TopMetal2', direction='x'):
    ports = simulation_setup.all_simulation_ports()
    for n in numbers:
        ports.add_port(simulation_setup.simulation_port(portnumber=n, voltage=voltage, port_Z0=50, source_layernum=200 + n,
                                                        target_layername=target, direction=direction))
    return ports


def gssg(length=300.0, port_depth=0.0, grounds=True):
    """GSSG lines drawn to the layout edge at x = 0, ports on 201, 202 (zero depth: a line along the edge)"""
    ap = all_polygons_list()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(0, y0, length, y1, TM2)
        ap.add_rectangle(0, y0, port_depth, y1, 201 + k)
    if grounds:
        for y0, y1 in GSSG_GROUNDS:
            ap.add_rectangle(0, y0, length, y1, TM2)
    return ap


def analyze(stack, ap, ports, boundary=BOUNDARY, fmax=100e9, **kw):
    materials, dielectrics, metals = stack
    return calibration.analyze_port_walls(ap, metals, materials, dielectrics, ports, boundary, fmax, 1e-6, **kw)


def test_gssg_drawn_to_the_edge(stack):
    r = analyze(stack, gssg(), ports_for([1, 2]))
    g = r['groups'][0]
    assert g['side'] == 'xmin' and g['ports'] == [1, 2]
    assert g['D'] == pytest.approx(50.0) and g['L'] == pytest.approx(200.0) and g['L_rule'] == '4 D'
    assert all(p['gap'] == pytest.approx(50 / 32, abs=1e-3) and p['gap_origin'] == 'tool' for p in g['port_details'])
    assert g['ground_layers'] == ['TopMetal2'] and g['valid_to_GHz'] == pytest.approx(100.0)
    assert r['warnings'] == []


def test_gap_from_the_drawing(stack):
    g = analyze(stack, gssg(port_depth=1.0), ports_for([1, 2]))['groups'][0]
    assert all(p['gap'] == pytest.approx(1.0) and p['gap_origin'] == 'drawing' for p in g['port_details'])


def test_line_drawn_short_of_the_edge(stack):
    ap = all_polygons_list()
    ap.add_rectangle(1.0, -5, 300, 5, TM2)
    ap.add_rectangle(0, -5, 0, 5, 201)
    for y0, y1 in ((-60, -15), (15, 60)):
        ap.add_rectangle(0, y0, 300, y1, TM2)
    g = analyze(stack, ap, ports_for([1]))['groups'][0]
    assert g['port_details'][0]['gap'] == pytest.approx(1.0) and g['port_details'][0]['gap_origin'] == 'drawing'


def test_strip_over_plate(stack):
    ap = all_polygons_list()
    ap.add_rectangle(0, -5, 300, 5, TM2)
    ap.add_rectangle(0, -5, 1, 5, 201)
    ap.add_rectangle(0, -150, 300, 150, SUBGND)
    g = analyze(stack, ap, ports_for([1]))['groups'][0]
    assert g['D'] == pytest.approx(10 + 2 * 11.2303, abs=1e-3) and g['ground_layers'] == ['SUBGND']


def test_wide_rectangle_is_harmless(stack):
    ap = gssg()
    ap.polygons = [p for p in ap.polygons if p.layernum not in (201, 202)]
    ap.add_rectangle(0, -20, 1, -2, 201)        # wider than line 1, but within the gaps to ground and to line 2
    ap.add_rectangle(0, 5, 1, 15, 202)
    g = analyze(stack, ap, ports_for([1, 2]))['groups'][0]
    assert g['port_details'][0]['line'] == [-15.0, -5.0]


def test_rectangle_over_two_metal_regions(stack):
    ap = gssg()
    ap.polygons = [p for p in ap.polygons if p.layernum != 201]
    ap.add_rectangle(0, -30, 1, -5, 201)        # over line 1 and ground
    with pytest.raises(calibration.PortWallError, match='separate TopMetal2 regions'):
        analyze(stack, ap, ports_for([1, 2]))


def test_no_ground_at_the_cut(stack):
    with pytest.raises(calibration.PortWallError, match='no ground metal reaches the wall'):
        analyze(stack, gssg(grounds=False), ports_for([1, 2]))


def test_line_at_an_angle(stack):
    ap = all_polygons_list()
    ap.add_polygon([[0, -5], [0, 5], [300, 305], [300, 295]], TM2)
    ap.add_rectangle(0, -5, 1, 5, 201)
    for y0, y1 in ((-60, -15), (15, 60)):
        ap.add_rectangle(0, y0, 300, y1, TM2)
    with pytest.raises(calibration.PortWallError, match='changes within D/4'):
        analyze(stack, ap, ports_for([1]))


def test_stacked_line_with_via_array(stack):
    ap = gssg()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(0, y0, 300, y1, TM1)
        x = 0.5
        while x < 300:
            ap.add_rectangle(x, y0 + 1, x + 1, y1 - 1, TV2)
            x += 3
    r = analyze(stack, ap, ports_for([1, 2]))
    stack_layers = {s[0] for s in r['groups'][0]['port_details'][0]['stack']}
    assert stack_layers == {'TopMetal2', 'TopVia2', 'TopMetal1'}
    assert any('solid bars' in w for w in r['warnings'])
    # the gap is cut out of all three layers
    _, _, metals = stack
    calibration.apply_port_walls(r, ap, metals, ports_for([1, 2]))
    gap = r['groups'][0]['port_details'][0]['gap']
    for layer in (TM2, TM1, TV2):
        assert all(not (p.xmin < gap - 1e-6 and p.ymax > -15 + 1e-6 and p.ymin < -5 - 1e-6) for p in ap.polygons
                   if p.layernum == layer)


def test_passive_port_on_a_wall(stack):
    with pytest.raises(calibration.PortWallError, match='passive'):
        analyze(stack, gssg(), ports_for([1, 2], voltage=0))


def via_ports(numbers, from_layer, to_layer, direction='z'):
    ports = simulation_setup.all_simulation_ports()
    for n in numbers:
        ports.add_port(simulation_setup.simulation_port(portnumber=n, voltage=1, port_Z0=50, source_layernum=200 + n,
                                                        from_layername=from_layer, to_layername=to_layer, direction=direction))
    return ports


M3 = 30


def gssg_over_metal3():
    """the 60 GHz PA case: TopMetal2 lines over a Metal3 plane, via ports Metal3 -> TopMetal2 along the edge"""
    ap = gssg()
    ap.add_rectangle(0, -65, 300, 65, M3)
    return ap


def test_via_port_on_a_wall_becomes_a_gap_port(stack):
    materials, dielectrics, metals = stack
    ap, ports = gssg_over_metal3(), via_ports([1, 2], 'Metal3', 'TopMetal2')
    r = analyze(stack, ap, ports)
    g = r['groups'][0]
    assert [p['target_layer'] for p in g['port_details']] == ['TopMetal2', 'TopMetal2']
    assert any('via port Metal3 -> TopMetal2 on port wall xmin, used as a gap port on TopMetal2' in n for n in r['notes'])
    assert not any('polarity' in n for n in r['notes'])
    calibration.apply_port_walls(r, ap, metals, ports)
    port = ports.get_port_by_number(1)
    assert (port.target_layername, port.from_layername, port.direction) == ('TopMetal2', None, 'x')


def test_via_port_drawn_from_the_line_to_ground_is_reversed(stack):
    r = analyze(stack, gssg_over_metal3(), via_ports([1, 2], 'Metal3', 'TopMetal2', direction='-z'))
    assert any('polarity was from the line to ground' in n for n in r['notes'])


def test_via_port_with_a_line_at_both_ends_is_refused(stack):
    ap = gssg()
    for y0, y1 in GSSG_LINES:
        ap.add_rectangle(0, y0, 300, y1, TM1)          # a TopMetal1 line under each TopMetal2 line
    with pytest.raises(calibration.PortWallError, match='both ends'):
        analyze(stack, ap, via_ports([1, 2], 'TopMetal1', 'TopMetal2'))


def test_via_port_drawn_as_a_point_is_refused(stack):
    ap = gssg_over_metal3()
    ap.polygons = [p for p in ap.polygons if p.layernum not in (201, 202)]
    ap.add_rectangle(0, -10, 0, -10, 201)
    ap.add_rectangle(0, 10, 0, 10, 202)
    with pytest.raises(calibration.PortWallError, match='drawn as a point'):
        analyze(stack, ap, via_ports([1, 2], 'Metal3', 'TopMetal2'))


def test_port_wall_without_port(stack):
    with pytest.raises(calibration.PortWallError, match='has no port'):
        analyze(stack, gssg(), ports_for([1, 2]), boundary=['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC'])


def test_port_wall_on_z(stack):
    with pytest.raises(calibration.PortWallError, match='xmin, xmax, ymin or ymax'):
        calibration.port_wall_sides(['ABC', 'ABC', 'ABC', 'ABC', 'PORTWALL', 'ABC'])


def test_port_on_an_edge_that_is_not_a_port_wall(stack):
    ap = gssg()
    ap.add_rectangle(100, 65, 110, 70, TM2)
    ap.add_rectangle(100, 70, 110, 70, 203)
    r = analyze(stack, ap, ports_for([1, 2, 3]))
    assert any('port 3 lies on the layout edge at ymax, which is not a port wall' in n for n in r['notes'])


def test_device_close_to_the_wall(stack):
    """the coil of the study: the ground strips end 50 from the wall, the coil is 130 wide"""
    ap = gssg(length=60)
    ap.polygons = [p for p in ap.polygons if not (p.layernum == TM2 and abs(p.ymin) > 20)]
    for y0, y1 in GSSG_GROUNDS:
        ap.add_rectangle(0, y0, 50, y1, TM2)
    ap.add_rectangle(60, -60, 180, 60, TM2)
    r = analyze(stack, ap, ports_for([1, 2]))
    assert any('less than D' in w for w in r['warnings']) and any('mirrors' in w for w in r['warnings'])
    with pytest.raises(calibration.PortWallError, match='past the uniform feed'):
        analyze(stack, ap, ports_for([1, 2]), reference_plane_shift={'xmin': 55})
    r = analyze(stack, ap, ports_for([1, 2]), reference_plane_shift={'xmin': 30})
    assert r['groups'][0]['shift'] == 30 and any('reference plane shifted' in w for w in r['warnings'])


def test_standards_shortened_at_high_frequency(stack):
    g = analyze(stack, gssg(length=900), ports_for([1, 2]), fmax=200e9)['groups'][0]
    assert g['L'] < 200 and g['L_rule'] == 'wavelength / 5' and g['L'] >= 100


def test_box_settings_of_a_port_wall():
    margin, air, boundary, log = calibration.port_wall_box(['xmin'], (100, 100, 100, 100), 50, BOUNDARY)
    assert margin == (0, 100, 100, 100) and air == [0, 50, 50, 50, 50, 50] and boundary[0] == 'PEC'
    assert 'not used' in log[0]


def test_direction_set_and_standard_geometry(stack):
    materials, dielectrics, metals = stack
    ap = gssg()
    ports = ports_for([1, 2], direction='-x')
    r = analyze(stack, ap, ports)
    calibration.apply_port_walls(r, ap, metals, ports)
    assert [p.direction for p in ports.ports] == ['x', 'x']
    g = r['groups'][0]
    calibration.standard_records(r, 'dev')
    polygons, std_ports = calibration.standard_model(g, 2, metals)
    assert polygons.get_bounding_box() == (0.0, 400.0, -65.0, 65.0)
    assert [(p.portnumber, p.direction) for p in std_ports.ports] == [(1, 'x'), (3, '-x'), (2, 'x'), (4, '-x')]
    lines = [p for p in polygons.polygons if p.layernum == TM2 and p.ymin == -15]
    assert lines[0].xmin == pytest.approx(g['port_details'][0]['gap']) and lines[0].xmax == pytest.approx(400 - lines[0].xmin)


def test_model_files_and_run_script(stack, tmp_path):
    """the whole flow with gmsh: device, two standards, keys, port_information.json, run_sim"""
    materials, dielectrics, metals = stack
    ap = gssg(length=250)
    ports = ports_for([1, 2])
    sim_path = utilities.create_sim_path(str(tmp_path), 'line', dirname='palace_model')
    settings = dict(unit=1e-6, margin=100, air_around=50, boundary=BOUNDARY, fstart=0, fstop=100e9, fstep=5e9,
                    refined_cellsize=4, meshsize_max=70, order=1, no_gui=True, no_preview=True,
                    simulation_ports=ports, materials_list=materials, dielectrics_list=dielectrics, metals_list=metals,
                    allpolygons=ap, sim_path=sim_path, model_basename='line')
    simulation_setup.create_palace(ports.all_active_excitations(), settings)
    utilities.create_run_script(sim_path)
    files = set(os.listdir(sim_path))
    for name in ('config.json', 'config_cal_xmin_L.json', 'config_cal_xmin_2L.json', 'line_cal_xmin_L.msh',
                 'line_cal_xmin_2L.msh', 'cal_xmin_L.key', 'cal_xmin_2L.key', 'port_information.json'):
        assert name in files
    info = json.load(open(os.path.join(sim_path, 'port_information.json')))
    assert info['port_walls'][0]['ports'] == [1, 2] and info['port_walls'][0]['standards'][1]['length'] == 400
    std = json.load(open(os.path.join(sim_path, 'config_cal_xmin_L.json')))
    assert std['Solver']['Driven']['Samples'] == [{'Type': 'Point', 'Freq': [5.0, 20.0, 100.0], 'SaveStep': 0}]
    assert std['Problem']['Output'] == 'output/line_cal_xmin_L' and len(std['Boundaries']['LumpedPort']) == 4
    run = open(os.path.join(sim_path, 'run_sim')).read()
    assert run.index('config_cal_xmin_L.json') < run.index('config_cal_xmin_2L.json') < run.index('run_palace config.json')


def test_both_ends_of_a_line_share_the_standards(stack, tmp_path):
    ap = gssg()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(300, y0, 300, y1, 203 + k)
    ports = ports_for([1, 2, 3, 4])
    boundary = ['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC']
    r = analyze(stack, ap, ports, boundary=boundary)
    margin, air, bc, _ = calibration.port_wall_box(['xmin', 'xmax'], (100, 100, 100, 100), 50, boundary)
    calibration.standard_records(r, 'line', margin, air, bc)
    xmin, xmax = r['groups']
    assert xmax['shared_with'] == 'xmin' and xmax['standards'] == xmin['standards']
    (tmp_path / 'port_information.json').write_text(json.dumps({'port_walls': calibration.port_information_record(r)}))
    lines = calibration.run_script_lines(str(tmp_path))
    assert sum('run_palace' in line for line in lines) == 2


def test_ports_on_the_layout_edge_without_port_walls():
    ap = gssg()
    ap.add_rectangle(100, 65, 110, 70, TM2)
    ap.add_rectangle(100, 70, 110, 70, 203)
    ap.add_rectangle(150, -5, 150, 5, 204)          # inside the layout
    ports = ports_for([1, 2, 3, 4])
    assert calibration.ports_on_layout_edge(ap, ports) == {1: 'xmin', 2: 'xmin', 3: 'ymax'}


def test_vias_away_from_the_wall_are_not_part_of_the_line(stack):
    """a line that steps down to TopMetal1 further in (60 GHz PA layout): D must come from the line at the wall"""
    ap = gssg()
    for y0, y1 in GSSG_LINES:
        ap.add_rectangle(60, y0, 300, y1, TM1)
        ap.add_rectangle(62, y0 + 1, 64, y1 - 1, TV2)
    g = analyze(stack, ap, ports_for([1, 2]))['groups'][0]
    assert g['D'] == pytest.approx(50.0) and {s[0] for s in g['port_details'][0]['stack']} == {'TopMetal2'}


def test_target_that_is_not_a_metal(stack):
    with pytest.raises(calibration.PortWallError, match='LBE is not a metal layer'):
        analyze(stack, gssg(), ports_for([1, 2], target='LBE'))


def test_errors_per_wall_with_collect_errors(stack):
    ap = gssg()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(300, y0, 300, y1, 203 + k)
    ports = ports_for([1, 2, 3, 4])
    ports.ports[0].target_layername = 'LBE'
    r = analyze(stack, ap, ports, boundary=['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC'], collect_errors=True)
    assert [g['side'] for g in r['groups']] == ['xmax'] and 'LBE is not a metal layer' in r['errors']['xmin']


def test_walls_a_few_nm_apart_share_the_standards(stack):
    """layout tools leave a few nm between the two ends of a line (60 GHz PA layout: 15 nm)"""
    ap = all_polygons_list()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(0, y0, 150, y1, TM2)
        ap.add_rectangle(150, y0 + 0.015, 300, y1 + 0.015, TM2)
        ap.add_rectangle(0, y0, 0, y1, 201 + k)
        ap.add_rectangle(300, y0 + 0.015, 300, y1 + 0.015, 203 + k)
    for y0, y1 in GSSG_GROUNDS:
        ap.add_rectangle(0, y0, 300, y1, TM2)
    boundary = ['PORTWALL', 'PORTWALL', 'ABC', 'ABC', 'ABC', 'ABC']
    r = analyze(stack, ap, ports_for([1, 2, 3, 4]), boundary=boundary)
    margin, air, bc, _ = calibration.port_wall_box(['xmin', 'xmax'], (100, 100, 100, 100), 50, boundary)
    calibration.standard_records(r, 'line', margin, air, bc)
    assert r['groups'][1].get('shared_with') == 'xmin'
