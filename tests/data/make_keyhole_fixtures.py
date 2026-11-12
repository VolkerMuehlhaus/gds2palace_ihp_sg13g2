"""Writes the fixture layouts with holes for tests/test_reader_fixtures.py. GDSII has no holes: a writer encodes one as a
single boundary with a slit to the outline, and KLayout and gdspy place that slit differently. The same shapes are
therefore written by both.

    klayout -b -r make_keyhole_fixtures.py      -> keyholes_klayout.gds, keyholes.json (shapes and KLayout's areas)
    python make_keyhole_fixtures.py             -> keyholes_gdspy.gds, via_bridge.gds

A case is (add - sub) + add2, all lists of polygons in um, drawn on Metal1 (8/0) at its own x offset.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LAYER, PITCH = 8, 400.0


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def octagon(r):
    a = r * 0.41421356
    a = round(a, 3)
    return [[-a, -r], [a, -r], [r, -a], [r, a], [a, r], [-a, r], [-r, a], [-r, -a]]


def shifted(polygon, dx, dy):
    return [[x + dx, y + dy] for x, y in polygon]


CASES = {
    # the dipole ground plane: a strip from the plane edge into a slot
    'slot_with_strip': {'add': [box(0, 0, 300, 200)], 'sub': [box(50, 40, 250, 160)], 'add2': [box(140, 100, 160, 160)]},
    # strips from every side, so that the slit passes a strip root whichever side the writer picks
    'slot_with_four_strips': {'add': [box(0, 0, 300, 200)], 'sub': [box(50, 40, 250, 160)],
                              'add2': [box(140, 110, 160, 160), box(140, 40, 160, 90), box(50, 95, 120, 105),
                                       box(180, 95, 250, 105)]},
    # two slots with a strip each, the strips in line (the full dipole plane)
    'two_slots_with_strips': {'add': [box(0, 0, 300, 300)], 'sub': [box(50, 30, 250, 130), box(50, 170, 250, 270)],
                              'add2': [box(140, 80, 160, 130), box(140, 170, 160, 220)]},
    # several holes at the same height: one slit can run through all of them
    'holes_in_a_row': {'add': [box(0, 0, 300, 100)], 'sub': [box(30 + 60 * k, 30, 60 + 60 * k, 70) for k in range(4)],
                       'add2': []},
    # a 3 x 3 field of holes (cheesing)
    'hole_field': {'add': [box(0, 0, 200, 200)],
                   'sub': [box(30 + 55 * i, 30 + 55 * j, 60 + 55 * i, 60 + 55 * j) for i in range(3) for j in range(3)],
                   'add2': []},
    # a hole that touches the outline in one point
    'hole_touching_outline': {'add': [box(0, 0, 200, 200)], 'sub': [[[0, 100], [60, 60], [120, 100], [60, 140]]],
                              'add2': []},
    # two holes that touch each other in one point
    'holes_touching': {'add': [box(0, 0, 300, 200)], 'sub': [box(50, 50, 150, 100), box(150, 100, 250, 150)],
                       'add2': []},
    # a ring with an island in its hole, and a ring around both
    'nested_rings': {'add': [box(0, 0, 300, 300)], 'sub': [box(30, 30, 270, 270)],
                     'add2': [box(60, 60, 240, 240)], 'sub2': [box(90, 90, 210, 210)], 'add3': [box(130, 130, 170, 170)]},
    # slanted edges: an octagon ring (inductor turn) with a strip into the hole
    'octagon_ring_with_strip': {'add': [shifted(octagon(150), 150, 150)], 'sub': [shifted(octagon(120), 150, 150)],
                                'add2': [box(145, 150, 155, 275)]},
}


def write_klayout():
    import pya
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell('KEYHOLES')
    layer = layout.layer(LAYER, 0)
    areas = {}

    def region(polygons, dx):
        r = pya.Region()
        for p in polygons:
            r.insert(pya.DPolygon([pya.DPoint(x + dx, y) for x, y in p]).to_itype(layout.dbu))
        return r

    for index, (name, case) in enumerate(CASES.items()):
        dx = index * PITCH
        shape = region(case['add'], dx) - region(case['sub'], dx) + region(case.get('add2', []), dx)
        shape = shape - region(case.get('sub2', []), dx) + region(case.get('add3', []), dx)
        shape.merge()
        top.shapes(layer).insert(shape)
        areas[name] = shape.area() * layout.dbu ** 2
    layout.write(os.path.join(HERE, 'keyholes_klayout.gds'))
    with open(os.path.join(HERE, 'keyholes.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'layer': LAYER, 'pitch': PITCH, 'cases': CASES, 'klayout_area': areas}, f, indent=1)
        f.write('\n')


def write_gdspy():
    import gdspy
    library = gdspy.GdsLibrary(unit=1e-6, precision=1e-9)
    top = library.new_cell('KEYHOLES')
    for index, case in enumerate(CASES.values()):
        dx = index * PITCH
        move = lambda polygons: [shifted(p, dx, 0) for p in polygons]
        shape = gdspy.boolean(move(case['add']), move(case['sub']), 'not', max_points=0)
        for operation, key in (('or', 'add2'), ('not', 'sub2'), ('or', 'add3')):
            if case.get(key):
                shape = gdspy.boolean(shape, move(case[key]), operation, max_points=0)
        for points in shape.polygons:
            top.add(gdspy.Polygon(points, layer=LAYER, datatype=0))
    library.write_gds(os.path.join(HERE, 'keyholes_gdspy.gds'))


def write_via_bridge():
    """two lines 1 um apart on Metal1 (8) and Metal2 (10), a row of Via1 (19) on each next to the gap, and an
    in-plane port (201) across the gap at one end: for via_bridge_model.py"""
    import gdspy
    library = gdspy.GdsLibrary(unit=1e-6, precision=1e-9)
    top = library.new_cell('VIA_BRIDGE')
    for x0, x1 in ((0, 10), (11, 21)):
        for layer in (8, 10):
            top.add(gdspy.Rectangle((x0, 0), (x1, 40), layer=layer))
    for k in range(20):
        for x in (9.4, 11.41):
            top.add(gdspy.Rectangle((x, 5.4 + 1.5 * k), (x + 0.19, 5.59 + 1.5 * k), layer=19))
    top.add(gdspy.Rectangle((10, 0), (11, 4), layer=201))
    library.write_gds(os.path.join(HERE, 'via_bridge.gds'))


if __name__ == '__main__' or 'pya' in dir():
    try:
        import pya  # noqa: F401  (inside KLayout)
        write_klayout()
    except ImportError:
        write_gdspy()
        write_via_bridge()
