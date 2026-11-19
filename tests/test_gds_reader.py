"""Polygon repair in util_gds_reader: the repaired pieces must be the same shape as the polygon read.

    python -m pytest tests/test_gds_reader.py
"""
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from gds2palace import util_gds_reader as reader

# A ground plane with two slots and, in each slot, a strip that reaches in from the plane edge. KLayout writes the
# slit to the lower slot along the slot edge, so the boundary passes the root of that strip twice.
PLANE_WITH_STRIPS = [
    (-427.72, -750.0), (-427.72, -50.0), (458.5, -50.0), (458.5, -239.5), (438.5, -239.5), (438.5, -50.0),
    (0.0, -50.0), (0.0, -450.0), (800.0, -450.0), (800.0, -50.0), (-427.72, -50.0), (-427.72, 450.0), (0.0, 450.0),
    (0.0, 50.0), (438.5, 50.0), (438.5, 239.5), (458.5, 239.5), (458.5, 50.0), (800.0, 50.0), (800.0, 450.0),
    (-427.72, 450.0), (-427.72, 750.0), (1250.0, 750.0), (1250.0, -750.0)]


def test_slit_along_hole_edge_keeps_strip():
    expected = (box(-427.72, -750, 1250, 750) - box(0, 50, 800, 450) - box(0, -450, 800, -50)
                ).union(box(438.5, 50, 458.5, 239.5)).union(box(438.5, -239.5, 458.5, -50))
    pieces = reader._fracture_valid_pieces(PLANE_WITH_STRIPS)
    assert pieces is not None
    polygons = [Polygon(p) for p in pieces]
    assert all(p.is_valid for p in polygons)
    assert unary_union(polygons).symmetric_difference(expected).area < 1e-6


def test_repair_does_not_split_into_pieces_of_five_points():
    """gdspy did not return for a plain 12-vertex polygon with max_points=5 (seen on an Activ shape of the MIM
    example), so the repair must not go that low: a hang there would have no message"""
    import inspect
    candidates = inspect.signature(reader._fracture_valid_pieces).parameters['max_points_candidates'].default
    assert min(candidates) >= 6


def test_read_gds_takes_the_design_cell(tmp_path):
    """Without a cell name: the largest top-level cell, not $$$CONTEXT_INFO$$$ or a small device cell placed nowhere,
    whatever their order in the file. A named cell is taken as it is."""
    import gdstk
    lib = gdstk.Library()
    lib.new_cell('$$$CONTEXT_INFO$$$').add(gdstk.rectangle((0, 0), (1000, 1000), layer=1))
    lib.new_cell('small_device').add(gdstk.rectangle((0, 0), (2, 2), layer=8))
    lib.new_cell('DESIGN').add(gdstk.rectangle((0, 0), (50, 40), layer=8))
    path = str(tmp_path / 'multi.gds')
    lib.write_gds(path)
    assert gdstk.read_gds(path).top_level()[0].name != 'DESIGN'
    library = gdstk.read_gds(path)
    assert reader.select_design_cell(library).name == 'DESIGN'
    assert reader.select_design_cell(library, 'small_device').name == 'small_device'
    assert reader.select_design_cell(library, 'nope').name == 'DESIGN'
    from gds2palace import stackup_reader, utilities
    _, _, metals = stackup_reader.read_substrate(utilities.get_stackup_path('SG13G2_FEM_200um.xml'))
    result = reader.read_gds(path, [8], purposelist=[0], metals_list=metals)
    assert result.get_bounding_box() == pytest.approx((0, 50, 0, 40))
