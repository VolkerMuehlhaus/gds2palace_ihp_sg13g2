"""Polygon repair in util_gds_reader: the repaired pieces must be the same shape as the polygon read.

    python -m pytest tests/test_gds_reader.py
"""
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
