"""The GDS reader on layouts with awkward hole encodings (tests/data). GDSII has no holes: a writer encodes one as a
single boundary with a slit, and the reader has to turn that back into the drawn shape. The expected shapes are built
here from the shape definitions (shapely on plain boxes), and the areas are KLayout's own.

    python -m pytest tests/test_reader_fixtures.py
"""
import json
import os

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

import example_runner as er
from gds2palace import util_gds_reader as reader

with open(os.path.join(er.DATA, 'keyholes.json'), encoding='utf-8') as f:
    KEYHOLES = json.load(f)
WRITERS = ['klayout', 'gdspy']
DIPOLE = os.path.join(er.DATA, 'dipole_port_sg13_forPalace_em.gds')
M1 = 8


def expected_shape(name):
    case = KEYHOLES['cases'][name]
    dx = list(KEYHOLES['cases']).index(name) * KEYHOLES['pitch']
    part = lambda key: unary_union([Polygon([(x + dx, y) for x, y in p]) for p in case.get(key, [])])
    return part('add').difference(part('sub')).union(part('add2')).difference(part('sub2')).union(part('add3'))


@pytest.fixture(scope='module', params=WRITERS)
def keyholes(request):
    return er.read_layout(os.path.join(er.DATA, f'keyholes_{request.param}.gds'))


@pytest.mark.parametrize('name', list(KEYHOLES['cases']))
def test_hole_encodings(keyholes, name):
    expected = expected_shape(name)
    assert expected.area == pytest.approx(KEYHOLES['klayout_area'][name], rel=1e-9), 'fixture definition vs KLayout'
    x0, y0, x1, y1 = expected.bounds
    got = er.returned_shape(keyholes, M1).intersection(box(x0 - 10, y0 - 10, x1 + 10, y1 + 10))
    assert er.changed_area(got, expected) == 0, f'returned area {got.area:.6g}, drawn {expected.area:.6g}'


def test_hole_encodings_against_the_file(keyholes):
    problems, skipped = er.compare_with_layout(keyholes)
    assert problems == [] and skipped == []


def test_dipole_plane_keeps_both_strips():
    """the layout of the 0.10.3 fix: KLayout's slit to the lower slot runs along the slot edge, past the strip root"""
    call = er.read_layout(DIPOLE, extra_layers=[201])
    problems, skipped = er.compare_with_layout(call)
    assert problems == [] and skipped == []
    plane = er.returned_shape(call, M1)
    assert plane.area == pytest.approx(1677.72 * 1500 - 2 * (800 * 400 - 20 * 189.5), rel=1e-9)
    assert plane.contains(box(439, 51, 458, 239)) and plane.contains(box(439, -239, 458, -51))
    assert sum(int(p.layernum) == 201 for p in call['result'].polygons) == 1      # the zero-width via port


# ---- the checks above must fail for the bug they are there for ----

def test_checks_catch_the_lost_strip(monkeypatch):
    """With the 0.10.3 fix switched off (the repair trusts make_valid() again), the reader loses the strip in the
    dipole plane and in the KLayout fixtures: the comparison with the layout has to report that."""
    class WithoutReference:
        def __getattr__(self, name):
            return getattr(gdspy_module, name)

        @staticmethod
        def boolean(a, b, operation, **kwargs):
            if b is None and operation == 'or' and kwargs.get('max_points') == 199:
                return None         # the area reference of the fix
            return gdspy_module.boolean(a, b, operation, **kwargs)

    gdspy_module = reader.gdspy
    monkeypatch.setattr(reader, 'gdspy', WithoutReference())
    dipole = er.read_layout(DIPOLE)
    keyholes = er.read_layout(os.path.join(er.DATA, 'keyholes_klayout.gds'))
    monkeypatch.undo()
    problems, _ = er.compare_with_layout(dipole)
    assert len(problems) == 1 and problems[0].startswith('layer 8: returned shape differs'), problems
    assert '3790' in problems[0]                                          # the 20 x 189.5 um strip
    problems, _ = er.compare_with_layout(keyholes)
    assert problems and problems[0].startswith('layer 8: returned shape differs'), problems
