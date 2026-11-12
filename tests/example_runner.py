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
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

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
        os.chdir(state[0])
        sys.argv[:], sys.path[:] = state[1], state[2]
        run.log = output.getvalue()
    return run


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


def returned_shape(call, layer):
    """shapely geometry of what read_gds() returned on a layer. A piece may be a plain keyhole (one boundary with a
    slit), which shapely cannot take as it is: each piece is first cut into simple polygons with gdspy."""
    pieces = []
    for p in call['result'].polygons:
        if int(p.layernum) == layer:
            simple = gdspy.boolean([np.column_stack((p.pts_x, p.pts_y))], None, 'or', max_points=5,
                                   precision=GRID / 10)
            pieces.extend(ShapelyPolygon(q).buffer(0) for q in simple.polygons)
    return unary_union(pieces)


def changed_area(a, b):
    """area of the difference between two shapely shapes that is wider than rounding (see _difference)"""
    return a.symmetric_difference(b).buffer(-SLIVER).buffer(SLIVER).area
