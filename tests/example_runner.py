"""Runs the model scripts shipped with gds2palace inside the tests and compares what they build with the layout.

A script is executed as it is (runpy), with a few gds2palace functions wrapped: read_gds() and create_palace() are
recorded, output goes to a temporary folder, and no gmsh window opens. The checks compare with values computed here
from the GDSII file, not with results stored from an earlier run.
"""
import contextlib
import io
import os
import runpy
import sys
import tomllib

import gdspy
import gmsh
import numpy as np
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import box as shapely_box
from shapely.strtree import STRtree
from shapely.ops import polygonize, unary_union

from gds2palace import gds_reader, simulation_setup, utilities

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
DATA = os.path.join(TESTS, 'data')
GRID = 0.001             # gdspy's booleans (in the reader and here) snap to this grid, in layout units
SLIVER = 2 * GRID        # a difference thinner than twice this is rounding along an edge, not a changed shape


def load_manifest():
    with open(os.path.join(TESTS, 'examples.toml'), 'rb') as f:
        return tomllib.load(f)['example']


class ExampleRun:
    def __init__(self):
        self.read_calls = []        # {'filename', 'layerlist', 'kwargs', 'result'} per read_gds() call
        self.create_calls = []      # settings of each create_palace() call
        self.sim_path = None
        self.log = ''
        self.groups = []            # the gmsh physical groups of each model built, see model_groups()
        self.nets = []              # separate conductor nets of each model built, see model_nets()


def run_example(script, tmp_path, mode='reader'):
    """Run a model script. mode 'reader': stop before the model is built (create_palace does nothing);
    'geometry': build the gmsh geometry without meshing; 'model': the full model files."""
    script = os.path.join(REPO, script)
    run = ExampleRun()
    run.sim_path = str(tmp_path)
    original = {'read_gds': gds_reader.read_gds, 'create_palace': simulation_setup.create_palace,
                'create_sim_path': utilities.create_sim_path, 'create_run_script': utilities.create_run_script}

    def read_gds(filename, layerlist, *args, **kwargs):
        if args:
            raise AssertionError('read_gds called with more than two positional arguments: not recorded by the tests')
        result = original['read_gds'](filename, layerlist, **kwargs)
        run.read_calls.append({'filename': os.path.abspath(filename), 'layerlist': list(layerlist),
                               'kwargs': kwargs, 'result': result})
        return result

    def create_palace(excite_ports, settings):
        run.create_calls.append(settings)
        if mode == 'reader':
            return '', run.sim_path
        settings['no_gui'] = True
        if mode == 'geometry':
            settings['preview_only'] = True
        return original['create_palace'](excite_ports, settings)

    def create_sim_path(script_path, model_basename, dirname='palace_model'):
        return original['create_sim_path'](run.sim_path, model_basename, dirname)

    def create_run_script(*args, **kwargs):
        if mode == 'model':
            return original['create_run_script'](*args, **kwargs)

    def clear():
        # create_model() ends with gmsh.clear(): the last moment the finished geometry can be read
        run.groups.append(model_groups())
        run.nets.append(model_nets(run.groups[-1], run.create_calls[-1]['metals_list']))
        gmsh_clear()

    gmsh_clear = gmsh.clear
    gmsh.clear = clear
    state = (os.getcwd(), list(sys.argv), list(sys.path))
    output = io.StringIO()
    gds_reader.read_gds, simulation_setup.create_palace = read_gds, create_palace
    utilities.create_sim_path, utilities.create_run_script = create_sim_path, create_run_script
    try:
        os.chdir(os.path.dirname(script))
        sys.argv = [script]
        with contextlib.redirect_stdout(output):
            runpy.run_path(script, run_name='__main__')
    finally:
        gds_reader.read_gds, simulation_setup.create_palace = original['read_gds'], original['create_palace']
        utilities.create_sim_path, utilities.create_run_script = original['create_sim_path'], original['create_run_script']
        gmsh.clear = gmsh_clear
        os.chdir(state[0])
        sys.argv[:], sys.path[:] = state[1], state[2]
        run.log = output.getvalue()
    return run


def model_groups():
    """{(dim, name): {'entities', 'mass', 'bbox'}} of the physical groups in the current gmsh model: mass is the
    volume of a 3D group and the area of a 2D group, in layout units"""
    groups = {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        entities = [int(e) for e in gmsh.model.getEntitiesForPhysicalGroup(dim, tag)]
        boxes = np.array([gmsh.model.getBoundingBox(dim, e) for e in entities])
        groups[(dim, gmsh.model.getPhysicalName(dim, tag))] = {
            'entities': entities,
            'mass': float(sum(gmsh.model.occ.getMass(dim, e) for e in entities)),
            'bbox': [*boxes[:, :3].min(axis=0), *boxes[:, 3:].max(axis=0)] if len(entities) else None}
    return groups


# ----------------------------------------- layout reference -----------------------------------------

def raw_layout(filename, cellname=''):
    """{layer: {datatype: [point arrays]}} of the cell that read_gds() reads, flattened - read here with gdspy only"""
    library = gdspy.GdsLibrary(infile=filename)
    cell = library.cells.get(cellname, library.top_level()[0])
    out = {}
    for (layer, datatype), polygons in cell.get_polygons(by_spec=True).items():
        out.setdefault(int(layer), {}).setdefault(int(datatype), []).extend(polygons)
    return out


def _area(polygons):
    if not polygons:
        return 0.0
    merged = gdspy.boolean(polygons, None, 'or', max_points=0)
    return 0.0 if merged is None else merged.area()


def _difference(a, b, operation):
    """(area, bounds of the largest piece) of a xor b / a not b, counting only what is wider than rounding: where
    the reader cuts a polygon into pieces, new points on slanted edges are snapped to gdspy's grid, which leaves
    slivers of a fraction of a grid step along those edges."""
    result = gdspy.boolean(a, b, operation, max_points=0, precision=GRID / 10)
    if result is None:
        return 0.0, None
    shape = unary_union([ShapelyPolygon(p).buffer(0) for p in result.polygons]).buffer(-SLIVER)
    if shape.is_empty:
        return 0.0, None
    parts = list(shape.geoms) if hasattr(shape, 'geoms') else [shape]
    largest = max(parts, key=lambda g: g.area).buffer(SLIVER)
    return float(sum(g.buffer(SLIVER).area for g in parts)), [round(v, 3) for v in largest.bounds]


def _bbox(polygons):
    points = np.vstack(polygons)
    return [float(v) for v in (*points.min(axis=0), *points.max(axis=0))]


def compare_with_layout(call):
    """Problems (list of str, empty if none) of one recorded read_gds() call: for each layer read, the polygons
    returned must be the shape drawn in the GDSII file. Also returns the list of layers that were not compared."""
    kwargs = call['kwargs']
    if kwargs.get('mirror') or kwargs.get('offset_x') or kwargs.get('offset_y') or kwargs.get('layernumber_offset'):
        return [], ['all (mirror / offset / layer number offset in use)']
    metals = kwargs.get('metals_list')
    purposes = list(kwargs.get('purposelist', [0]))
    merge = kwargs.get('merge_polygon_size', 0)
    derived = getattr(metals, 'derived_layers', None) if metals is not None else None
    derived_numbers = set(derived.getlayernumbers()) if derived is not None and derived.derived_layers else set()
    solid = set(metals.getlayernumbers()) if metals is not None else set()
    boundary = {int(layer) for layer in kwargs.get('gds_boundary_layers', [])}

    raw = raw_layout(call['filename'], kwargs.get('cellname', ''))
    returned = {}
    for p in call['result'].polygons:
        returned.setdefault(int(p.layernum), []).append(np.column_stack((p.pts_x, p.pts_y)))

    problems, skipped = [], []
    layers = list(dict.fromkeys(list(call['layerlist']) + sorted(boundary) + sorted(returned)))
    for layer in layers:
        if layer in derived_numbers:
            if returned.get(layer):         # computed from other layers: nothing drawn to compare with
                skipped.append(f'{layer} (derived layer)')
            continue
        drawn = [p for datatype in purposes for p in raw.get(layer, {}).get(datatype, [])]
        got = returned.get(layer, [])
        if not drawn and not got:
            continue
        if not drawn or not got:
            problems.append(f'layer {layer}: {len(drawn)} polygon(s) drawn, {len(got)} returned')
            continue
        if layer not in solid and layer not in boundary:
            # port and marker layers: shapes are passed on as drawn (a via port may be a zero-width line)
            if len(drawn) != len(got) or not np.allclose(_bbox(drawn), _bbox(got), atol=1e-6):
                problems.append(f'layer {layer} (port/marker): {len(drawn)} shape(s) {_bbox(drawn)} drawn, '
                                f'{len(got)} shape(s) {_bbox(got)} returned')
            continue
        area = _area(drawn)
        metal = metals.getbylayernumber(layer) if metals is not None else None
        if merge > 0 and metal is not None and getattr(metal, 'is_via', False):
            # merged via arrays: the gaps are filled, so the result covers the vias and is not smaller
            lost, where = _difference(drawn, got, 'not')
            if lost:
                problems.append(f'layer {layer} (merged vias): {lost:.6g} of {area:.6g} drawn area not covered, '
                                f'largest piece at {where}')
            continue
        changed, where = _difference(drawn, got, 'xor')
        if changed:
            problems.append(f'layer {layer}: returned shape differs from the drawn one by {changed:.6g} '
                            f'(drawn area {area:.6g}, returned {_area(got):.6g}), largest piece at {where}')
    return problems, skipped


# ----------------------------------------- fixtures -----------------------------------------

def read_layout(gds, stackup='SG13G2_FEM_200um.xml', merge_polygon_size=0, extra_layers=()):
    """read_gds() on a layout as a model script calls it; returns the record that compare_with_layout() takes"""
    from gds2palace import stackup_reader
    materials, dielectrics, metals = stackup_reader.read_substrate(utilities.get_stackup_path(stackup))
    layers = metals.getlayernumbers() + list(extra_layers)
    kwargs = {'purposelist': [0], 'metals_list': metals, 'merge_polygon_size': merge_polygon_size,
              'gds_boundary_layers': dielectrics.get_boundary_layers()}
    with contextlib.redirect_stdout(io.StringIO()):
        result = gds_reader.read_gds(gds, layers, **kwargs)
    return {'filename': os.path.abspath(gds), 'layerlist': layers, 'kwargs': kwargs, 'result': result}


def _winding_number(x, y, ring):
    """how often the closed ring (n x 2 array) goes around the point"""
    x0, y0 = ring[:, 0] - x, ring[:, 1] - y
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    cross = x0 * y1 - x1 * y0
    up = (y0 <= 0) & (y1 > 0) & (cross > 0)
    down = (y0 > 0) & (y1 <= 0) & (cross < 0)
    return int(up.sum() - down.sum())


def filled_shape(points):
    """shapely geometry of the area a GDSII boundary fills, also for a boundary that touches or overlaps itself (a
    hole written with a slit). Independent of the reader's repair and of gdspy: the boundary is split where it meets
    itself, and each enclosed face counts if the boundary goes around it (non-zero winding)."""
    ring = np.asarray(points, dtype=float)
    polygon = ShapelyPolygon(ring)
    if polygon.is_valid:
        return polygon
    closed = LineString(np.vstack([ring, ring[:1]]))
    faces = [face for face in polygonize(unary_union(closed))
             if _winding_number(*face.representative_point().coords[0], ring) != 0]
    return unary_union(faces)


def returned_shape(call, layer):
    """shapely geometry of what read_gds() returned on a layer"""
    return unary_union([filled_shape(np.column_stack((p.pts_x, p.pts_y)))
                        for p in call['result'].polygons if int(p.layernum) == layer])


def changed_area(a, b):
    """area of the difference between two shapely shapes that is wider than rounding (see _difference)"""
    return a.symmetric_difference(b).buffer(-SLIVER).buffer(SLIVER).area


# ----------------------------------------- model geometry -----------------------------------------

REL = 1e-6               # relative tolerance of areas and volumes read from gmsh


def _close(value, expected):
    return abs(value - expected) <= REL * max(abs(expected), 1e-9)


def _model_box(groups):
    boxes = np.array([g['bbox'] for (dim, _), g in groups.items() if dim == 3])
    return [*boxes[:, :3].min(axis=0), *boxes[:, 3:].max(axis=0)]


def compare_with_model(call, settings, groups):
    """Problems (list of str) of the gmsh model built from one read_gds() call: every stackup layer with shapes must be
    in the model with the size that follows from the layout and the stackup. Also returns what was not compared.

    conductor with the surface model: the faces of the body, 2 x area + perimeter x thickness (faces on the outer
    boundary of the model are left out by gds2palace); via, or conductor solved inside: volume = area x thickness."""
    metals = call['kwargs']['metals_list']
    layers = {int(p.layernum) for p in call['result'].polygons}
    x0, y0, _, x1, y1, _ = np.round(_model_box(groups), 6)      # gmsh boxes carry a 1e-7 margin
    outline = shapely_box(x0, y0, x1, y1).exterior
    problems, skipped = [], []

    for metal in metals.metals:
        number = int(metal.layernum)
        if number not in layers:
            continue
        shape = returned_shape(call, number)
        surfaces = {key: g for key, g in groups.items()
                    if key[0] == 2 and key[1].startswith(metal.name + '_') and key[1][len(metal.name) + 1:].isdigit()}
        volume = groups.get((3, metal.name))
        sheet = groups.get((2, metal.name))
        if not surfaces and volume is None and sheet is None:
            problems.append(f'{metal.name}: {shape.area:.6g} drawn, but not in the model')
            continue
        if sheet is not None:           # a layer without thickness: one face, the drawn shape
            if not _close(sheet['mass'], shape.area):
                problems.append(f"{metal.name}: sheet area {sheet['mass']:.8g}, drawn {shape.area:.8g}")
            continue
        if not metal.thickness:
            skipped.append(f'{metal.name} (no thickness, and not a sheet group)')
            continue
        found = list(surfaces.values()) + ([volume] if volume is not None else [])
        boxes = np.array([g['bbox'] for g in found])
        got_box = [*boxes[:, :3].min(axis=0), *boxes[:, 3:].max(axis=0)]
        bx0, by0, bx1, by1 = shape.bounds
        want_box = [bx0, by0, metal.zmin, bx1, by1, metal.zmax]
        if not np.allclose(got_box, want_box, atol=2e-3):
            problems.append(f'{metal.name}: bounding box {np.round(got_box, 3).tolist()}, '
                            f'from layout and stackup {np.round(want_box, 3).tolist()}')
        if volume is not None:
            if not _close(volume['mass'], shape.area * metal.thickness):
                problems.append(f"{metal.name}: volume {volume['mass']:.8g}, from the layout "
                                f'{shape.area * metal.thickness:.8g} (area {shape.area:.8g} x {metal.thickness:.4g})')
        else:
            on_boundary = shape.boundary.intersection(outline).length
            want = 2 * shape.area + (shape.length - on_boundary) * metal.thickness
            got = sum(g['mass'] for g in surfaces.values())
            if not _close(got, want):
                problems.append(f'{metal.name}: surface {got:.8g}, from the layout {want:.8g} '
                                f'(area {shape.area:.8g}, perimeter {shape.length:.8g}, thickness {metal.thickness:.4g})')

    for metal in metals.metals:
        if int(metal.layernum) not in layers and any(
                name == metal.name or (name.startswith(metal.name + '_') and name[len(metal.name) + 1:].isdigit())
                for _, name in groups):
            problems.append(f'{metal.name}: in the model, but nothing returned by the reader on layer {metal.layernum}')

    for port in settings['simulation_ports'].ports:
        key = (2, f'P{port.portnumber}')
        drawn = [p for p in call['result'].polygons if int(p.layernum) == int(port.source_layernum)]
        if key not in groups:
            problems.append(f'port {port.portnumber}: not in the model ({len(drawn)} shape(s) on layer '
                            f'{port.source_layernum})')
            continue
        if not drawn:
            problems.append(f'port {port.portnumber}: in the model, but nothing drawn on layer {port.source_layernum}')
            continue
        if port.target_layername is not None:
            want = sum((p.xmax - p.xmin) * (p.ymax - p.ymin) for p in drawn)
        else:
            a, b = metals.getbylayername(port.from_layername), metals.getbylayername(port.to_layername)
            lower, upper = (a, b) if a.zmin < b.zmin else (b, a)
            want = sum(max(p.xmax - p.xmin, p.ymax - p.ymin) for p in drawn) * (upper.zmin - lower.zmax)
        if not _close(groups[key]['mass'], want):
            problems.append(f"port {port.portnumber}: area {groups[key]['mass']:.8g}, from layout and stackup {want:.8g}")
    scripted = {f'P{port.portnumber}' for port in settings['simulation_ports'].ports}
    extra = sorted(name for dim, name in groups if dim == 2 and name[:1] == 'P' and name[1:].isdigit()
                   and name not in scripted)
    if extra:
        problems.append(f'port group(s) {extra} in the model without a port in the script')
    return problems, skipped


def layout_nets(call):
    """Number of separate conductor nets in the layout as drawn in the GDSII file (not as returned by the reader, so
    that a via array merged across two nets or a lost shape shows up): shapes on one layer that touch are one piece,
    and pieces on two layers are connected where they overlap and the layers meet in z (a via on a metal).
    A derived layer has nothing drawn; its shapes are taken from the reader."""
    kwargs = call['kwargs']
    metals = kwargs['metals_list']
    raw = raw_layout(call['filename'], kwargs.get('cellname', ''))
    pieces = []                     # (metal, shapely polygon)
    for number in sorted({int(p.layernum) for p in call['result'].polygons}):
        drawn = [p for datatype in kwargs.get('purposelist', [0]) for p in raw.get(number, {}).get(datatype, [])]
        shape = unary_union([filled_shape(p) for p in drawn]) if drawn else returned_shape(call, number)
        for metal in metals.getallbylayernumber(number) or []:
            if getattr(metal, 'is_dielectric', False):
                continue
            pieces += [(metal, part) for part in (shape.geoms if hasattr(shape, 'geoms') else [shape])]
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    tree = STRtree([part for _, part in pieces])
    for i, (metal, part) in enumerate(pieces):
        for j in tree.query(part):
            other = pieces[j][0]
            if j <= i or other is metal:
                continue
            meet = abs(metal.zmax - other.zmin) < 1e-6 or abs(other.zmax - metal.zmin) < 1e-6 or \
                (metal.zmin < other.zmax and other.zmin < metal.zmax)
            if meet and part.intersection(pieces[j][1]).area > 0:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(len(pieces))})


def model_nets(groups, metals):
    """Number of separate conductor nets in the current gmsh model: the faces of the conductor groups and of the via
    volumes, connected where they share an edge (after the fragment in gds2palace, touching bodies share faces and
    edges)."""
    names = {m.name for m in metals.metals if not getattr(m, 'is_dielectric', False)}
    bodies = []                     # each a list of face tags that belong together
    for (dim, name), group in groups.items():
        if dim == 3 and name in names:
            bodies += [[abs(t) for _, t in gmsh.model.getBoundary([(3, v)], oriented=False)] for v in group['entities']]
        elif dim == 2 and (name in names or name.rpartition('_')[0] in names):
            bodies += [[face] for face in group['entities']]
    parent = {}

    def find(i):
        while parent.setdefault(i, i) != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for faces in bodies:
        for face in faces:
            parent[find(('f', face))] = find(('f', faces[0]))
            for _, curve in gmsh.model.getBoundary([(2, face)], oriented=False):
                parent[find(('c', abs(curve)))] = find(('f', face))
    return len({find(key) for key in list(parent) if key[0] == 'f'})
