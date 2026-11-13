"""Port walls in gds2palace (util_calibration.py): finding the wall ports, the gap, D, the length of the standards, the
errors and warnings, the standards' geometry, and the model files. Layouts are built in memory; the last test meshes a
small line with gmsh (no Palace).

    python -m pytest tests/test_port_walls.py
"""
import json
import os
import re

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
    assert any('solid bars' in n for n in r['notes']) and not any('solid bars' in w for w in r['warnings'])
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
    """the coil of the study: the ground strips end 45 from the wall (less than D = 50), the coil is 130 wide"""
    ap = gssg(length=60)
    ap.polygons = [p for p in ap.polygons if not (p.layernum == TM2 and abs(p.ymin) > 20)]
    for y0, y1 in GSSG_GROUNDS:
        ap.add_rectangle(0, y0, 45, y1, TM2)
    ap.add_rectangle(60, -60, 180, 60, TM2)
    r = analyze(stack, ap, ports_for([1, 2]))
    assert any('less than D' in n for n in r['notes']) and any('mirrors' in n for n in r['notes']) and r['warnings'] == []
    with pytest.raises(calibration.PortWallError, match='past the uniform feed'):
        analyze(stack, ap, ports_for([1, 2]), reference_plane_shift={'xmin': 55})
    r = analyze(stack, ap, ports_for([1, 2]), reference_plane_shift={'xmin': 30})
    assert r['groups'][0]['shift'] == 30 and any('reference plane shifted' in n for n in r['notes'])


def coil_turn_next_to_the_wall(gap_to_turn=3.0, turn_width=1.0):
    """a strip over a Metal3 plane from the wall, and a coil's outer turn along the wall: a bar narrower than the
    scan's D/8 grid, gap_to_turn from the wall (the intra_matching_diff case)"""
    ap = all_polygons_list()
    ap.add_rectangle(0, -60, 200, 60, M3)
    ap.add_rectangle(0, -1.5, 100, 1.5, TM2)
    ap.add_rectangle(0, -1.5, 0, 1.5, 201)
    ap.add_rectangle(gap_to_turn, 1.5, gap_to_turn + turn_width, 50, TM2)       # the turn, joined to the strip
    ap.add_rectangle(gap_to_turn, -50, gap_to_turn + turn_width, -1.5, TM2)
    return ap


def test_a_narrow_turn_next_to_the_wall_is_found(stack):
    """the scan samples just past every vertex: a 1 um bar 3 from the wall (D/4 = 4.6, the grid D/8 = 2.3) is not
    stepped over"""
    ap = coil_turn_next_to_the_wall()
    with pytest.raises(calibration.PortWallError, match='changes within D/4'):
        analyze(stack, ap, via_ports([1], 'Metal3', 'TopMetal2'))


def test_an_extension_accepts_metal_close_to_the_wall(stack):
    """with the port wall moved outward, the extension is the straight feed the standards need: metal close to the
    layout edge belongs to the device next to the reference plane, accepted without a warning"""
    ap = coil_turn_next_to_the_wall()
    r = analyze(stack, ap, via_ports([1], 'Metal3', 'TopMetal2'), port_wall_extension={'xmin': 50})
    g = r['groups'][0]
    assert g['uniform_from_wall'] == pytest.approx(3.0, abs=0.01) and g['extension'] == 50
    assert r['warnings'] == [] and not r['errors']
    r = analyze(stack, ap, via_ports([1], 'Metal3', 'TopMetal2'), port_wall_extension={'xmin': 'auto'})
    assert r['groups'][0]['extension'] > 0 and not r['errors']
    # an extension shorter than what is missing to D/4 is still an error, and the message names the length needed
    D = g['D']
    with pytest.raises(calibration.PortWallError, match='moved outward by at least'):
        analyze(stack, ap, via_ports([1], 'Metal3', 'TopMetal2'), port_wall_extension={'xmin': D / 4 - 3.0 - 0.5})


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
    # the model carries the combine script of the gds2palace that wrote it; run_sim warns about a wrapper that
    # would not use it
    assert 'combine_extend_snp.py' in files
    assert run.index('run_palace config.json') < run.index('WARNING: your combine_snp') < run.rindex('combine_snp\n')
    assert open(os.path.join(sim_path, 'combine_extend_snp.py')).read() == \
        open(os.path.join(utilities.get_scripts_dir(), 'combine_extend_snp.py')).read()


@pytest.mark.parametrize('display, windows', [(None, 0), (':0', 1)])
def test_no_gmsh_window_without_display(stack, tmp_path, monkeypatch, display, windows):
    """a script without no_gui (e.g. exported from setupEM) on Linux with no display: no gmsh window"""
    import sys
    import gmsh
    materials, dielectrics, metals = stack
    ports = ports_for([1, 2])
    opened = []
    monkeypatch.setattr(gmsh.fltk, 'run', lambda: opened.append(1))
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    if display:
        monkeypatch.setenv('DISPLAY', display)
    else:
        monkeypatch.delenv('DISPLAY', raising=False)
    sim_path = utilities.create_sim_path(str(tmp_path), 'line', dirname='palace_model')
    settings = dict(unit=1e-6, margin=100, air_around=50, boundary=BOUNDARY, fstart=0, fstop=100e9, fstep=5e9,
                    refined_cellsize=4, meshsize_max=70, order=1, preview_only=True,
                    simulation_ports=ports, materials_list=materials, dielectrics_list=dielectrics, metals_list=metals,
                    allpolygons=gssg(length=250), sim_path=sim_path, model_basename='line')
    simulation_setup.create_palace(ports.all_active_excitations(), settings)
    assert len(opened) == windows


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


def coil_like():
    """lines over the SUBGND plate, a device 20 from the wall: inside the fringe field and the wall's mirror range"""
    ap = all_polygons_list()
    for k, (y0, y1) in enumerate(GSSG_LINES):
        ap.add_rectangle(0, y0, 20, y1, TM2)
        ap.add_rectangle(0, y0, 0, y1, 201 + k)
    ap.add_rectangle(20, -40, 120, 40, TM2)                 # the device
    ap.add_rectangle(0, -60, 120, 60, SUBGND)
    return ap


def test_auto_extension_moves_the_port_wall(stack):
    materials, dielectrics, metals = stack
    ap, ports = coil_like(), ports_for([1, 2])
    plain = analyze(stack, coil_like(), ports_for([1, 2]))['groups'][0]
    assert any('less than D' in n and "'auto'" in n for n in plain['notes'])
    r = analyze(stack, ap, ports, port_wall_extension={'xmin': 'auto'})
    g = r['groups'][0]
    need = max(g['D'], 0.5 * g['device_size']) - g['uniform_from_wall']
    assert g['extension'] == pytest.approx(need, abs=0.011) and g['extension'] > 0
    assert not any('less than D' in n or 'mirrors' in n for n in g['notes']) and g['warnings'] == []
    assert any('port wall moved' in n for n in g['notes']) and not any('port wall moved' in w for w in g['warnings'])
    calibration.apply_port_walls(r, ap, metals, ports)
    E, gap = g['extension'], g['port_details'][0]['gap']
    assert ap.get_bounding_box()[0] == pytest.approx(-E)
    port = [p for p in ap.polygons if p.layernum == 201][0]
    assert (port.xmin, port.xmax) == (pytest.approx(-E), pytest.approx(-E + gap))
    lines = [p for p in ap.polygons if p.layernum == TM2 and p.ymin == -15]
    assert min(p.xmin for p in lines) == pytest.approx(-E + gap) and max(p.xmax for p in lines) == pytest.approx(20)
    assert any(p.xmin == pytest.approx(0) for p in lines), "no gap cut at the layout edge"
    assert calibration.port_information_record(r)[0]['extension'] == E


def test_extension_value_is_checked(stack):
    with pytest.raises(calibration.PortWallError, match="'auto' or a length"):
        analyze(stack, coil_like(), ports_for([1, 2]), port_wall_extension={'xmin': -5})
    with pytest.raises(calibration.PortWallError, match='not a port wall'):
        analyze(stack, coil_like(), ports_for([1, 2]), port_wall_extension={'ymin': 10})


def line_over_plane_with_slot(slot, closes_at=3.0, length=300.0):
    """a 10 um TopMetal2 line at y = -5..5 over a Metal1 plane that reaches the wall at x = 0, with a slot at
    y = slot (y0, y1) from the wall to x = closes_at; port 1 drawn on the wall"""
    ap = all_polygons_list()
    ap.add_rectangle(0, -5, length, 5, TM2)
    ap.add_rectangle(0, -5, 0, 5, 201)
    y0, y1 = slot
    ap.add_rectangle(0, -100, length, y0, M1)
    ap.add_rectangle(closes_at, y0, length, y1, M1)
    ap.add_rectangle(0, y1, length, 100, M1)
    return ap


def test_plane_slot_far_from_the_line_is_reported_not_an_error(stack):
    # the slot closes 3 um from the wall, within D/4, but it is farther from the line than D: outside the port's region,
    # a note (the far_change study: below the mesh noise), not a warning
    r = analyze(stack, line_over_plane_with_slot((60, 70)), ports_for([1]))
    g = r['groups'][0]
    assert g['D'] < 60 - 5
    assert not any('away from the lines changes' in w for w in r['warnings'])
    far = [n for n in r['notes'] if 'away from the lines changes' in n]
    assert far and 0 < float(re.search(r'changes ([\d.]+) from', far[0]).group(1)) <= 3
    assert not any('less than D' in n for n in r['notes'])      # no device seen within D along the line


def test_plane_slot_near_the_line_is_an_error(stack):
    with pytest.raises(calibration.PortWallError, match='within D/4'):
        analyze(stack, line_over_plane_with_slot((12, 20)), ports_for([1]))


def test_plane_slot_far_and_the_device_distance(stack):
    # the far slot does not count as the device: the device distance is where the line's own neighbourhood changes
    ap = line_over_plane_with_slot((60, 70))
    ap.add_rectangle(20, -40, 100, -20, TM2)                        # other metal 15 um beside the line, 20 um in (< D)
    r = analyze(stack, ap, ports_for([1]))
    dev = [n for n in r['notes'] if 'less than D' in n]
    assert dev and 10 < float(re.search(r'device is ([\d.]+) from', dev[0]).group(1)) <= 20


def test_wall_extension_continues_the_layout_edge(stack):
    """settings['wall_extension']: a wall that is not a port wall moved outward, for the pieces of a split region"""
    _, _, metals = stack
    ap = gssg()
    ap.add_rectangle(100, -200, 300, 200, M1)                   # a plane that doesn't reach xmin: not continued
    boundary = ['PEC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']
    log = calibration.extend_walls(ap, metals, {'xmin': 20.0}, boundary)
    assert ap.get_bounding_box()[0] == pytest.approx(-20.0)
    added = [p for p in ap.polygons if min(p.pts_x) == pytest.approx(-20.0)]
    assert len(added) == 4 and all(int(p.layernum) == TM2 and max(p.pts_x) == pytest.approx(0.0) for p in added)
    assert sorted((min(p.pts_y), max(p.pts_y)) for p in added) == sorted(GSSG_LINES + GSSG_GROUNDS)
    assert 'moved 20 outward' in log[0] and 'TopMetal2' in log[0] and 'Metal1' not in log[0]
    assert calibration.extend_walls(gssg(), metals, None, boundary) == []
    assert calibration.extend_walls(gssg(), metals, {'xmin': 0}, boundary) == []
    for value, side, bc, message in ((-1, 'xmin', boundary, 'length of 0 or more'), ('auto', 'xmin', boundary, 'length of 0 or more'),
                                     (20.0, 'zmax', boundary, 'can only be'), (20.0, 'xmin', BOUNDARY, 'use port_wall_extension')):
        with pytest.raises(calibration.PortWallError, match=message):
            calibration.extend_walls(gssg(), metals, {side: value}, bc)


def test_via_port_in_the_plane_of_a_pec_wall(stack, tmp_path, capsys):
    """a PEC wall at the layout edge shorts a via port drawn on that edge: found, and the model is not written"""
    materials, dielectrics, metals = stack
    ap = gssg()
    ap.add_rectangle(0, -200, 300, 200, M1)
    ap.add_rectangle(150, -5, 150, 5, 203)                      # a via port inside the layout
    ports = via_ports([1, 3], 'Metal1', 'TopMetal2')
    pec = ['PEC', 'ABC', 'ABC', 'ABC', 'ABC', 'ABC']
    found = lambda bc, margin, air, p=ports: calibration.via_ports_in_pec_walls(ap, p, dielectrics, bc, margin, air)
    assert found(pec, (0, 100, 100, 100), [0, 50, 50, 50, 50, 50]) == [(1, 'xmin')]
    assert found(pec, (100, 100, 100, 100), 50) == [], "a wall away from the layout edge"
    assert found(pec, (0, 100, 100, 100), 50) == [], "air between the layout edge and the wall"
    assert found(['PMC'] + pec[1:], (0, 100, 100, 100), [0, 50, 50, 50, 50, 50]) == [], "a PMC wall doesn't short it"
    assert found(pec, (0, 100, 100, 100), [0, 50, 50, 50, 50, 50], ports_for([1])) == [], "an in-plane port: a gap port to the wall"
    sim_path = utilities.create_sim_path(str(tmp_path), 'line', dirname='palace_model')
    settings = dict(unit=1e-6, margin=[0, 100, 100, 100], air_around=[0, 50, 50, 50, 50, 50], boundary=pec, fstart=0, fstop=100e9,
                    fstep=5e9, refined_cellsize=4, meshsize_max=70, order=1, no_gui=True, no_preview=True,
                    simulation_ports=ports, materials_list=materials, dielectrics_list=dielectrics, metals_list=metals,
                    allpolygons=ap, sim_path=sim_path, model_basename='line')
    with pytest.raises(SystemExit):
        simulation_setup.create_palace(ports.all_active_excitations(), settings)
    out = capsys.readouterr().out
    assert 'ERROR: port 1 is a via port in the plane of the PEC wall at xmin' in out and "Make xmin a port wall" in out
    assert not os.path.isfile(os.path.join(sim_path, 'config.json'))


def test_standards_of_a_wall_next_to_an_extended_wall_continue_the_metal(stack):
    """xmin is moved 20 outward: the plane that reaches xmin is continued, in the device and in the cross-section the
    standards of ymin extrude (their box is 20 wider on that side)"""
    ap = all_polygons_list()
    ap.add_rectangle(0, -200, 300, 200, M1)
    ap.add_rectangle(0, -5, 150, 5, TM2)
    ap.add_rectangle(0, -5, 0, 5, 201)
    ap.add_rectangle(250, -200, 260, -50, TM2)
    ap.add_rectangle(250, -200, 260, -200, 202)
    boundary = ['PORTWALL', 'ABC', 'PORTWALL', 'ABC', 'ABC', 'ABC']
    r = analyze(stack, ap, ports_for([1, 2]), boundary=boundary, port_wall_extension={'xmin': 20.0})
    xmin, ymin = r['groups']
    assert xmin['extension'] == 20.0 and ymin['transverse'] == pytest.approx([-20.0, 300.0])
    plane = [entry for entry in ymin['profile'] if entry[0] == 'Metal1']
    assert plane == [['Metal1', pytest.approx(-20.0), pytest.approx(300.0)]]
    line = [entry for entry in ymin['profile'] if entry[0] == 'TopMetal2']
    assert line == [['TopMetal2', pytest.approx(250.0), pytest.approx(260.0)]] and ymin['port_details'][0]['stack'] == line


def lines_over_plate(lines, length=3000.0):
    """TopMetal2 lines (y0, y1) over a Metal1 plate, drawn to the layout edge at x = 0, ports on 201.."""
    ap = all_polygons_list()
    for k, (y0, y1) in enumerate(lines):
        ap.add_rectangle(0, y0, length, y1, TM2)
        ap.add_rectangle(0, y0, 0, y1, 201 + k)
    ap.add_rectangle(0, min(y for y, _ in lines) - 200, length, max(y for _, y in lines) + 200, M1)
    return ap


def test_D_of_lines_far_apart_is_not_their_span(stack):
    """Lines far from each other against their distance to ground (resonator arms cut by a split region) each settle
    over their own cross-section: D is that of the largest group of coupled lines."""
    single = analyze(stack, lines_over_plate([(0, 10)]), ports_for([1]), fmax=10e9)['groups'][0]
    d = single['distance_to_ground']
    assert single['D'] == pytest.approx(10 + 2 * d) and len(single['clusters']) == 1
    # a close pair (gap d): one cluster, D from the common span, as before
    pair = analyze(stack, lines_over_plate([(0, 10), (10 + d, 20 + d)]), ports_for([1, 2]), fmax=10e9)['groups'][0]
    assert pair['D'] == pytest.approx(20 + d + 2 * d) and [c['ports'] for c in pair['clusters']] == [[1, 2]]
    # eight lines 10 d apart: every line on its own, D that of one line
    far = [(k * (10 + 10 * d), k * (10 + 10 * d) + 10) for k in range(8)]
    g = analyze(stack, lines_over_plate(far), ports_for(range(1, 9)), fmax=10e9)['groups'][0]
    assert g['D'] == pytest.approx(single['D']) and len(g['clusters']) == 8
    assert g['span'] == pytest.approx(far[-1][1]) and g['L'] == pytest.approx(single['L'])
    assert any('groups of coupled lines' in n for n in g['notes'])
    # mixed, as hairpin resonators: a close pair among far lines gives the pair's D
    mixed = [(0, 10), (10 + 10 * d, 20 + 10 * d), (20 + 11 * d, 30 + 11 * d), (30 + 21 * d, 40 + 21 * d)]
    g = analyze(stack, lines_over_plate(mixed), ports_for(range(1, 5)), fmax=10e9)['groups'][0]
    assert [c['ports'] for c in g['clusters']] == [[1], [2, 3], [4]]
    assert g['D'] == pytest.approx(pair['D'])


def gssg_with_passivation_oversize():
    """GSSG lines drawn to the layout edge at x = 0 with a conformal passivation as in SG13G2_FEM_200um_passi3D.xml:
    derived layer 900 = TopMetal2 grown by 0.6, which reaches 0.6 past the edge where the lines are cut"""
    ap = gssg()
    for y0, y1 in GSSG_LINES + GSSG_GROUNDS:
        ap.add_rectangle(-0.6, y0 - 0.6, 300.6, y1 + 0.6, 900)
    ap.derived_layernums = {900}
    return ap


def test_passivation_oversize_does_not_move_the_layout_edge(stack):
    """The layout edge of a port wall is the drawn one: a derived layer reaching past it (passi3D stackup, a line cut by
    the region box) must not move the wall away from the ports (klayout_em_export balun, 'port wall has no port')"""
    ap = gssg_with_passivation_oversize()
    assert ap.get_bounding_box()[0] == pytest.approx(-0.6)
    assert ap.get_drawn_bounding_box()[0] == pytest.approx(0.0)
    assert calibration.ports_on_layout_edge(ap, ports_for([1, 2])) == {1: 'xmin', 2: 'xmin'}
    g = analyze(stack, ap, ports_for([1, 2]))['groups'][0]
    assert g['side'] == 'xmin' and g['ports'] == [1, 2]


def test_derived_layers_cut_at_the_walls_only():
    ap = gssg_with_passivation_oversize()
    assert calibration.walls_at_layout_edge(BOUNDARY, [20] * 4, 20) == ['xmin']
    assert calibration.walls_at_layout_edge(['ABC', 'PEC', 'ABC', 'ABC', 'ABC', 'ABC'], [20, 0, 20, 20], 0) == ['xmax']
    assert calibration.walls_at_layout_edge(['ABC'] * 6, [20] * 4, 20, {'ymax': 5.0}) == ['ymax']
    # no wall at the layout edge, or no derived layers: nothing changes
    before = [(p.layernum, p.xmin, p.xmax, p.ymin, p.ymax) for p in ap.polygons]
    assert calibration.clip_derived_layers(ap, []) == []
    plain = gssg()
    assert calibration.clip_derived_layers(plain, ['xmin']) == []
    assert [(p.layernum, p.xmin, p.xmax, p.ymin, p.ymax) for p in ap.polygons] == before
    # a port wall at xmin: cut there, the other sides keep the oversize
    log = calibration.clip_derived_layers(ap, ['xmin'])
    assert log and '900' in log[0]
    passivation = [p for p in ap.polygons if p.layernum == 900]
    assert len(passivation) == 4
    assert all(p.xmin == pytest.approx(0.0) and p.xmax == pytest.approx(300.6) for p in passivation)
    assert ap.get_bounding_box() == pytest.approx((0.0, 300.6, -65.6, 65.6))


def test_read_gds_knows_the_derived_layers(tmp_path):
    """read_gds records the derived layers, so that the drawn layout edge leaves them out (passi3D stackup)"""
    import gdspy
    from gds2palace import gds_reader
    lib = gdspy.GdsLibrary()
    cell = lib.new_cell('TOP')
    cell.add(gdspy.Rectangle((0, -5), (100, 5), layer=TM2))
    cell.add(gdspy.Rectangle((0, -5), (0, 5), layer=201))
    gds = str(tmp_path / 'line.gds')
    lib.write_gds(gds)
    materials, dielectrics, metals = stackup_reader.read_substrate(utilities.get_stackup_path('SG13G2_FEM_200um_passi3D.xml'))
    ap = gds_reader.read_gds(gds, metals.getlayernumbers() + [201], purposelist=[0], metals_list=metals,
                             gds_boundary_layers=dielectrics.get_boundary_layers())
    assert 900 in ap.derived_layernums
    assert ap.get_bounding_box()[0] == pytest.approx(-0.6, abs=1e-3)
    assert ap.get_drawn_bounding_box() == pytest.approx((0.0, 100.0, -5.0, 5.0))
