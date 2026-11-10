########################################################################
#
# Copyright 2026 Volker Muehlhaus and IHP PDK Authors
#
# Licensed under the GNU General Public License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.gnu.org/licenses/gpl-3.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################

"""Calibrated de-embedding of ports at a port wall.

A port wall is a box side set to 'PORTWALL' in settings['boundary']: a PEC wall right at the layout edge, without
dielectric oversize and without air, where lines are cut. Every in-plane port whose polygon lies on that edge is a wall
port. Its polygon marks the line and the gap between the wall and the line, which is cut out of the metal here. All
wall ports on one side form one calibration group.

For each group, two standards are written into the device's _data folder: the layout's cross-section at the wall,
extruded to thru lines of length L and 2 L with ports at both ends, with the device's stackup and mesh settings, solved
at three frequencies. combine_extend_snp.py removes the port with the double delay method (Rautio) and writes the
de-embedded Touchstone file.

The rules come from test_data/port_deembedding_study (README.md, step 6):
  D      = span of the group's lines + 2 x distance to the nearest ground metal at the cut
  L      = 4 D, shortened to a fifth of the guided wavelength at the highest frequency (2 L <= 0.4 wavelengths), not
           below 2 D
  gap    = from the drawing, or D/32 when the line is drawn to the edge; a warning above D/10
  ground = metal that reaches the port wall next to the lines; without it the model is not written

Errors raise PortWallError; create_model() prints them and stops, setupEM shows them.
"""

import hashlib
import json
import math
import os

import numpy as np
import shapely
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon
from shapely.geometry import box as shapely_box

from .util_stackup_reader import PEC_MATERIAL_NAME

__version__ = "1.2.0"

C0 = 299792458.0
TOL = 1e-3                     # drawing units, the gmsh geometry tolerance
CUT_OFFSET = 0.01              # the cut profile is taken this far past the gap, drawing units
# neighbouring lines on one port wall count as coupled (one cluster, D from their common span) when they are closer
# than this many times their distance to ground (port_wall_cluster_study, 2026-11-11: a PCB pair over a plane and an
# on-chip GSSG pair, D per line against D as a pair: the differential mode agrees within the mesh noise, the common mode
# on chip within 4 x; a split hairpin filter joined from its pieces agrees with the full model)
COUPLED_WITHIN = 2.0
WALL_SIDES = ('xmin', 'xmax', 'ymin', 'ymax')
BOX_SIDES = ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax')
INWARD = {'xmin': 'x', 'xmax': '-x', 'ymin': 'y', 'ymax': '-y'}
OPPOSITE = {'xmin': 'xmax', 'xmax': 'xmin', 'ymin': 'ymax', 'ymax': 'ymin'}
TRANSVERSE = {'xmin': ('ymin', 'ymax'), 'xmax': ('ymin', 'ymax'), 'ymin': ('xmin', 'xmax'), 'ymax': ('xmin', 'xmax')}
STANDARD_PORT_LAYER = 60001    # port layers of the standards, in memory only
STANDARDS = (('L', 1), ('2L', 2))
STANDARD_FREQUENCY_FRACTIONS = (1 / 20, 1 / 5, 1)

# local frame per wall side: u from the wall into the layout, v along the wall (shapely affine parameters)
_TO_LOCAL = {'xmin': lambda w: [1, 0, 0, 1, -w, 0], 'xmax': lambda w: [-1, 0, 0, 1, w, 0],
             'ymin': lambda w: [0, 1, 1, 0, -w, 0], 'ymax': lambda w: [0, -1, 1, 0, w, 0]}
_TO_GLOBAL = {'xmin': lambda w: [1, 0, 0, 1, w, 0], 'xmax': lambda w: [-1, 0, 0, 1, w, 0],
              'ymin': lambda w: [0, 1, 1, 0, 0, w], 'ymax': lambda w: [0, 1, -1, 0, 0, w]}


class PortWallError(Exception):
    """A port wall that can't be calibrated: the message says why and what to change"""


# ------------------------------------------------------------------------------------------------------- box settings

def port_wall_sides(boundary):
    """Sides set to 'PORTWALL' in settings['boundary'] (6 values: xmin, xmax, ymin, ymax, zmin, zmax)"""
    sides = [side for side, value in zip(BOX_SIDES, boundary) if str(value).upper() == 'PORTWALL']
    for side in sides:
        if side not in WALL_SIDES:
            raise PortWallError(f"boundary {side} = 'PORTWALL': a port wall cuts lines in the layout plane, so it can only be "
                                f"xmin, xmax, ymin or ymax")
    return sides


def port_wall_box(sides, margin, air_around, boundary):
    """A port wall is PEC at the layout edge: dielectric oversize 0 and air 0 on that side, whatever the settings say for
    it (the margin and air lists always carry a value, so a conflict can't be told from the default).
    margin: (xmin, xmax, ymin, ymax); air_around: number or 6 values. Returns margin, air (6 values), boundary, log lines."""
    margin = list(margin)
    air = list(air_around) if isinstance(air_around, (list, tuple)) else [air_around] * 6
    boundary = ['PEC' if str(value).upper() == 'PORTWALL' else value for value in boundary]
    log = []
    for side in sides:
        i = BOX_SIDES.index(side)
        changed = []
        if margin[i] != 0:
            changed.append(f'dielectric oversize {margin[i]:g}')
        if air[i] != 0:
            changed.append(f'air {air[i]:g}')
        margin[i] = 0
        air[i] = 0
        log.append(f'Port wall {side}: PEC at the layout edge, no dielectric oversize, no air'
                   + (f" (the settings' {' and '.join(changed)} for {side} are not used)" if changed else ''))
    return tuple(margin), air, boundary, log


# ------------------------------------------------------------------------------------------------------- geometry

def _local(geom, side, wall):
    return affine_transform(geom, _TO_LOCAL[side](wall))


def _global(geom, side, wall):
    return affine_transform(geom, _TO_GLOBAL[side](wall))


def _local_bounds(poly, side, wall):
    """bounds (u0, v0, u1, v1) of a polygon in the local frame, from its points: works for zero-width port polygons"""
    a, b, d, e, xoff, yoff = _TO_LOCAL[side](wall)
    u = a * poly.pts_x + b * poly.pts_y + xoff
    v = d * poly.pts_x + e * poly.pts_y + yoff
    return float(u.min()), float(v.min()), float(u.max()), float(v.max())


def _shape(poly):
    shape = Polygon(np.column_stack((poly.pts_x, poly.pts_y)))
    if not shape.is_valid:
        shape = shape.buffer(0)
    return shape


class _Layers:
    """The stackup layers' polygons in the local frame of one wall side, with a search tree per layer"""

    def __init__(self, allpolygons, metals_list, side, wall):
        self.metals = metals_list.metals
        by_number = {}
        for poly in allpolygons.polygons:
            by_number.setdefault(int(poly.layernum), []).append(poly)
        self.geoms = {}
        self.trees = {}
        for metal in self.metals:
            number = int(metal.layernum)
            if number in self.geoms or number not in by_number:
                continue
            geoms = [_local(_shape(p), side, wall) for p in by_number[number]]
            geoms = [g for g in geoms if not g.is_empty]
            if geoms:
                self.geoms[number] = geoms
                self.trees[number] = shapely.STRtree(geoms)

    def vertex_us(self, u0, u1, vlo, vhi):
        """the distances from the wall of all polygon vertices with u0 < u < u1 and v in [vlo, vhi], sorted: where a
        cross-section can start to change (Manhattan geometry changes only there; an edge at an angle starts at one)"""
        found = set()
        region = shapely_box(u0, vlo, u1, vhi)
        for number, tree in self.trees.items():
            for i in tree.query(region):
                geom = self.geoms[number][i]
                for poly in getattr(geom, 'geoms', [geom]):
                    if poly.geom_type != 'Polygon':
                        continue
                    for ring in [poly.exterior] + list(poly.interiors):
                        for u, v in ring.coords:
                            if u0 < u < u1 and vlo - TOL <= v <= vhi + TOL:
                                found.add(round(u, 9))
        return sorted(found)

    def cut(self, number, u, vlo, vhi):
        """intervals in v of layer `number` on the line at distance u from the wall, merged, sorted"""
        if number not in self.geoms:
            return []
        line = LineString([(u, vlo - 1.0), (u, vhi + 1.0)])
        intervals = []
        for i in self.trees[number].query(line):
            part = self.geoms[number][i].intersection(line)
            for piece in getattr(part, 'geoms', [part]):
                if piece.is_empty or piece.geom_type not in ('LineString', 'LinearRing'):
                    continue
                _, v0, _, v1 = piece.bounds
                if v1 - v0 > TOL:
                    intervals.append((v0, v1))
        return _merge(intervals)

    def in_box(self, number, u0, v0, u1, v1):
        """the parts of layer `number` inside the box (local frame)"""
        if number not in self.geoms:
            return []
        region = shapely_box(u0, v0, u1, v1)
        parts = []
        for i in self.trees[number].query(region):
            part = self.geoms[number][i].intersection(region)
            if not part.is_empty and part.area > 0:
                parts.append(part)
        return parts

    def projection(self, number, u0, u1, vlo, vhi):
        """intervals in v covered by layer `number` anywhere between u0 and u1 (for via arrays)"""
        return _merge([(p.bounds[1], p.bounds[3]) for p in self.in_box(number, u0, vlo - 1.0, u1, vhi + 1.0)])

    def device_extent(self, u, ground):
        """v range of the device: the metal further than u from the wall, without the ground metal that reaches the wall
        (a ground plane spans the whole layout, but the wall mirrors the device's field, not the plane's).
        ground: {layer number: [intervals at the wall]}"""
        lo, hi = math.inf, -math.inf
        wall_line = LineString([(CUT_OFFSET, -1e12), (CUT_OFFSET, 1e12)])
        beyond = shapely_box(u + TOL, -1e12, 1e12, 1e12)
        for number, geoms in self.geoms.items():
            if number in ground:
                # a plane with openings is stored as several pieces: merge them, so that the whole connected plane
                # counts as ground when one piece of it reaches the wall
                merged = shapely.union_all(geoms)
                geoms = list(getattr(merged, 'geoms', [merged]))
            for g in geoms:
                if g.is_empty or g.bounds[2] <= u + TOL:
                    continue
                if number in ground and g.intersects(wall_line):
                    cut = g.intersection(wall_line).bounds
                    if any(_overlap((cut[1], cut[3]), iv) for iv in ground[number]):
                        continue
                part = g.intersection(beyond)
                if not part.is_empty:
                    lo, hi = min(lo, part.bounds[1]), max(hi, part.bounds[3])
        return (lo, hi) if lo < hi else None


def _merge(intervals):
    out = []
    for v0, v1 in sorted(intervals):
        if out and v0 <= out[-1][1] + TOL:
            out[-1] = (out[-1][0], max(out[-1][1], v1))
        else:
            out.append((v0, v1))
    return [(round(a, 6), round(b, 6)) for a, b in out]


def _clip(intervals, lo, hi):
    """the intervals cut to [lo, hi], empty ones dropped"""
    out = [(max(a, lo), min(b, hi)) for a, b in intervals]
    return [(a, b) for a, b in out if b - a > TOL]


def _overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0]) > TOL


def _same_profile(p, q):
    if set(p) != set(q):
        return False
    for key in p:
        if len(p[key]) != len(q[key]):
            return False
        for (a0, a1), (b0, b1) in zip(p[key], q[key]):
            if abs(a0 - b0) > 10 * TOL or abs(a1 - b1) > 10 * TOL:
                return False
    return True


def _is_conductor(metal, materials_list):
    if metal.is_metal or metal.is_via:
        return True
    if metal.is_sheet:
        if metal.material is not None and metal.material.strip().upper() == PEC_MATERIAL_NAME.upper():
            return True
        material = materials_list.get_by_name(metal.material)
        return material is not None and material.sigma > 1e4
    return False


def _z_touch(a, b):
    return a.zmin <= b.zmax + TOL and b.zmin <= a.zmax + TOL


# ------------------------------------------------------------------------------------------------------- analysis

def analyze_port_walls(allpolygons, metals_list, materials_list, dielectrics_list, simulation_ports, boundary, fmax,
                       unit=1e-6, reference_plane_shift=None, deembedding_length=None, collect_errors=False,
                       port_wall_extension=None):
    """Find the wall ports and everything the standards need. Changes nothing (setupEM's "Check port walls" calls only
    this). fmax in Hz, lengths in drawing units. Raises PortWallError; with collect_errors, an error that belongs to one
    port wall goes into result['errors'][side] instead, and the other walls are still analysed (setupEM).
    Returns {'groups': [...], 'warnings': [...], 'notes': [...], 'errors': {...}}, JSON-friendly."""
    sides = port_wall_sides(boundary)
    result = {'groups': [], 'warnings': [], 'notes': [], 'errors': {}}
    if not sides:
        return result
    reference_plane_shift = reference_plane_shift or {}
    for side in reference_plane_shift:
        if side not in sides:
            raise PortWallError(f"reference_plane_shift has a value for {side}, which is not a port wall")
    port_wall_extension = port_wall_extension or {}
    for side, value in port_wall_extension.items():
        if side not in sides:
            raise PortWallError(f"port_wall_extension has a value for {side}, which is not a port wall")
        if value != 'auto' and not (isinstance(value, (int, float)) and value >= 0):
            raise PortWallError(f"port_wall_extension for {side} must be 'auto' or a length of 0 or more, not {value!r}")
    for dielectric in dielectrics_list.dielectrics:
        if dielectric.gdsboundary is not None:
            raise PortWallError(f"dielectric {dielectric.name} has its own Boundary layer in the stackup; port walls need the "
                                f"dielectrics to end at the layout edge")
    if simulation_ports is None or len(getattr(simulation_ports, 'ports', [])) == 0:
        raise PortWallError("port walls are set, but the model has no ports")

    bxmin, bxmax, bymin, bymax = allpolygons.get_bounding_box()
    walls = {'xmin': bxmin, 'xmax': bxmax, 'ymin': bymin, 'ymax': bymax}
    transverse_range = {'xmin': (bymin, bymax), 'xmax': (bymin, bymax), 'ymin': (bxmin, bxmax), 'ymax': (bxmin, bxmax)}
    depth = {'xmin': bxmax - bxmin, 'xmax': bxmax - bxmin, 'ymin': bymax - bymin, 'ymax': bymax - bymin}

    # which ports lie on which layout edge
    port_polys = {}
    for poly in allpolygons.polygons:
        port_polys.setdefault(int(poly.layernum), []).append(poly)
    on_wall = {side: [] for side in sides}
    layers_of = {}
    for port in simulation_ports.ports:
        polys = port_polys.get(int(port.source_layernum), [])
        touching = set()
        for poly in polys:
            for side in WALL_SIDES:
                if _local_bounds(poly, side, walls[side])[0] <= TOL:
                    touching.add(side)
        walls_touched = sorted(touching & set(sides), key=WALL_SIDES.index)
        if not walls_touched:
            others = sorted(touching, key=WALL_SIDES.index)
            if others and port.target_layername is not None:
                result['notes'].append(f"port {port.portnumber} lies on the layout edge at {others[0]}, which is not a port "
                                       f"wall: it gets the estimated port inductance")
            continue
        if len(walls_touched) > 1:
            raise PortWallError(f"port {port.portnumber} touches two port walls ({' and '.join(walls_touched)}) at a corner; "
                                f"a wall port must lie on one side")
        if len(polys) > 1:
            raise PortWallError(f"port {port.portnumber} on port wall {walls_touched[0]} has {len(polys)} shapes on layer "
                                f"{port.source_layernum}; a wall port is one shape over one line")
        if abs(port.voltage) < 1e-6:
            raise PortWallError(f"port {port.portnumber} on port wall {walls_touched[0]} is passive (voltage 0); the "
                                f"calibration needs the full S-matrix, so every port must be excited")
        side = walls_touched[0]
        target, converted = port.target_layername, None
        if target is None:
            try:
                if side not in layers_of:
                    layers_of[side] = _Layers(allpolygons, metals_list, side, walls[side])
                target, converted = _via_port_as_gap_port(port, polys[0], side, walls[side], layers_of[side], metals_list,
                                                          transverse_range[side])
                result['notes'].append(converted)
            except PortWallError as error:
                if not collect_errors:
                    raise
                result['errors'].setdefault(side, str(error))
                continue
        on_wall[side].append((port, polys[0], target, converted))

    for side in sides:
        if side in result['errors']:
            continue
        try:
            if not on_wall[side]:
                raise PortWallError(f"port wall {side} has no port: draw the port polygons on the layout edge at {side}, "
                                    f"over the ends of the lines")
            result['groups'].append(_analyze_group(side, walls[side], on_wall[side], transverse_range[side], depth[side],
                                                   allpolygons, metals_list, materials_list, dielectrics_list, fmax, unit,
                                                   reference_plane_shift.get(side, 0.0), deembedding_length,
                                                   layers_of.get(side), port_wall_extension.get(side)))
        except PortWallError as error:
            if not collect_errors:
                raise
            result['errors'][side] = str(error)

    # an extension makes the box larger along the perpendicular walls: their standards need the same transverse box
    # and the metal that reaches such a wall is continued by its extension (apply_port_walls): in the cross-section the
    # standards extrude too, or their ground would end before the box does
    extended = {g['side']: g.get('extension', 0.0) for g in result['groups']}
    for g in result['groups']:
        lo, hi = TRANSVERSE[g['side']]
        v_lo, v_hi = g['transverse']
        e_lo, e_hi = extended.get(lo, 0.0), extended.get(hi, 0.0)
        for entry in g['profile'] + [s for p in g['port_details'] for s in p['stack']]:
            if e_lo and entry[1] <= v_lo + TOL:
                entry[1] = v_lo - e_lo
            if e_hi and entry[2] >= v_hi - TOL:
                entry[2] = v_hi + e_hi
        g['transverse'] = [v_lo - e_lo, v_hi + e_hi]

    # two port walls facing each other too close
    for side in ('xmin', 'ymin'):
        if side in sides and OPPOSITE[side] in sides:
            D = max((g['D'] for g in result['groups'] if g['side'] in (side, OPPOSITE[side])), default=0.0)
            apart = depth[side] + extended.get(side, 0.0) + extended.get(OPPOSITE[side], 0.0)
            if D and apart < 2 * D:
                result['warnings'].append(f"port walls {side} and {OPPOSITE[side]} are {apart:g} apart, less than 2 D = "
                                          f"{2 * D:g}: the coupling between them is not removed")
    for group in result['groups']:
        result['warnings'].extend(f"port wall {group['side']}: {w}" for w in group['warnings'])
        result['notes'].extend(f"port wall {group['side']}: {n}" for n in group.get('notes', []))
    return result


def _analyze_group(side, wall, ports, vrange, depth, allpolygons, metals_list, materials_list, dielectrics_list, fmax, unit,
                   shift, deembedding_length, layers=None, extension=None):
    vlo, vhi = vrange
    if layers is None:
        layers = _Layers(allpolygons, metals_list, side, wall)
    metal_of = {}
    for metal in metals_list.metals:
        metal_of.setdefault(int(metal.layernum), metal)
    conductors = {n: m for n, m in metal_of.items() if _is_conductor(m, materials_list)}
    # warnings: what makes the result wrong unless you act (shown in setupEM's status); notes: everything else that is
    # good to know (tooltip and log only). Few warnings, or nobody reads them
    warnings = []
    notes = []

    # 1. each port: the line, and the gap as drawn
    details = []
    for port, poly, target_name, converted in ports:
        _, pv0, u1, pv1 = _local_bounds(poly, side, wall)
        depth_drawn = max(u1, 0.0)
        if pv1 - pv0 < TOL:
            pv0, pv1 = pv0 - TOL, pv1 + TOL
        target = metals_list.getbylayername(target_name)
        if target is None:
            raise PortWallError(f"port {port.portnumber}: target layer {target_name} is not in the stackup")
        if target.is_via or not _is_conductor(target, materials_list):
            raise PortWallError(f"port {port.portnumber}: target layer {target.name} is not a metal layer; the target of "
                                f"a wall port is the metal of the line, e.g. TopMetal2")
        number = int(target.layernum)
        search = depth_drawn + max(10 * (pv1 - pv0), 0.1 * depth)
        parts = layers.in_box(number, -TOL, pv0, search, pv1)
        if not parts:
            raise PortWallError(f"port {port.portnumber} on port wall {side}: no {target.name} line found at the port polygon; "
                                f"draw the line to the layout edge and the port polygon over its end")
        u_start = max(min(p.bounds[0] for p in parts), 0.0)
        gap = max(depth_drawn, u_start)
        cut = layers.cut(number, gap + CUT_OFFSET, vlo, vhi)
        lines = [iv for iv in cut if _overlap(iv, (pv0, pv1)) or (iv[0] <= pv0 + TOL and iv[1] >= pv1 - TOL)]
        if not lines:
            raise PortWallError(f"port {port.portnumber} on port wall {side}: no {target.name} line found right behind the "
                                f"port polygon")
        if len(lines) > 1:
            raise PortWallError(f"port {port.portnumber} on port wall {side} touches {len(lines)} separate {target.name} "
                                f"regions; one port per line")
        details.append({'portnumber': port.portnumber, 'target_layer': target.name, 'target_number': number,
                        'depth_drawn': depth_drawn, 'u_start': u_start, 'gap': gap, 'line': list(lines[0]),
                        'line_start': u_start,
                        'converted': converted})
    details.sort(key=lambda d: d['line'][0])
    for a, b in zip(details, details[1:]):
        if a['target_number'] == b['target_number'] and _overlap(a['line'], b['line']):
            raise PortWallError(f"ports {a['portnumber']} and {b['portnumber']} on port wall {side} sit on the same line")

    # 2. signal stacks: the line and every conductor connected to it at the cut (stacked lines)
    # A via array under a stacked line is found within one line width of the cut (vias don't lie on the cut line),
    # and counts only if the metal on its other side is at the cut too: vias further in, where a line steps down to
    # the device, are not part of the line at the wall (they made D too small).
    u0 = max(d['gap'] for d in details) + CUT_OFFSET
    width = max(d['line'][1] - d['line'][0] for d in details)
    band = (u0, u0 + max(width, 10 * CUT_OFFSET))
    plain = {n: m for n, m in conductors.items() if not m.is_via}
    for d in details:
        stack = {d['target_number']: [tuple(d['line'])]}
        todo = [d['target_number']]
        while todo:
            n = todo.pop()
            for m, metal in conductors.items():
                if m == n or not _z_touch(metal, conductors[n]):
                    continue
                if metal.is_via:
                    vias = [iv for iv in layers.projection(m, band[0], band[1], vlo, vhi)
                            if any(_overlap(iv, s) for s in stack[n])]
                    # the metal on the via's other side, at the cut and over the via
                    for k, other in plain.items():
                        if k == n or not _z_touch(other, metal):
                            continue
                        beyond = [iv for iv in layers.cut(k, u0, vlo, vhi) if any(_overlap(iv, v) for v in vias)]
                        new = [iv for iv in beyond if iv not in stack.get(k, [])]
                        if new:
                            stack.setdefault(m, []).extend(v for v in vias if v not in stack.get(m, []))
                            stack.setdefault(k, []).extend(new)
                            todo.append(k)
                else:
                    found = [iv for iv in layers.cut(m, u0, vlo, vhi) if any(_overlap(iv, s) for s in stack[n])]
                    new = [iv for iv in found if iv not in stack.get(m, [])]
                    if new:
                        stack.setdefault(m, []).extend(new)
                        todo.append(m)
        d['stack'] = {n: _merge(ivs) for n, ivs in stack.items()}
    signal = {}
    for d in details:
        for n, ivs in d['stack'].items():
            signal.setdefault(n, []).extend(ivs)

    # 3. ground: conductor metal at the cut that is not a line and reaches the wall
    ground = []
    for n, metal in conductors.items():
        if metal.is_via:
            continue
        at_wall = layers.cut(n, CUT_OFFSET, vlo, vhi)
        for iv in layers.cut(n, u0, vlo, vhi):
            if any(_overlap(iv, s) for s in signal.get(n, [])):
                continue
            if any(_overlap(iv, w) for w in at_wall):
                ground.append((n, iv))
    port_names = ', '.join(str(d['portnumber']) for d in details)
    if not ground:
        raise PortWallError(f"port wall {side}: no ground metal reaches the wall next to ports {port_names}. The calibration "
                            f"needs return metal at the cut, ground strips or a plane. Bring ground metal to the layout edge "
                            f"there, move the cut, or don't use a port wall on {side}")

    # 4. D: span of the lines + 2 x distance to the nearest ground, per cluster of coupled lines; the largest counts.
    # Lines far from each other against their distance to ground (resonator arms over a plane, cut by a split) each
    # settle over their own cross-section: their common span is no measure of the port's size
    def rect(n, iv):
        m = metal_of[n]
        return iv[0], iv[1], m.zmin, m.zmax
    def distance(a, b):
        dv = max(0.0, b[0] - a[1], a[0] - b[1])
        dz = max(0.0, b[2] - a[3], a[2] - b[3])
        return math.hypot(dv, dz)
    d_min = math.inf
    zs = [math.inf, -math.inf]
    for d in details:
        rects = [rect(n, iv) for n, ivs in d['stack'].items() for iv in ivs]
        box = (min(r[0] for r in rects), max(r[1] for r in rects), min(r[2] for r in rects), max(r[3] for r in rects))
        zs = [min(zs[0], box[2]), max(zs[1], box[3])]
        d_line = math.inf
        for n, iv in ground:
            dist = distance(box, rect(n, iv))
            if dist < TOL:
                raise PortWallError(f"port {d['portnumber']} on port wall {side}: its line touches ground metal at the cut")
            d_line = min(d_line, dist)
        d['box'], d['d_ground'] = box, d_line
        d_min = min(d_min, d_line)
    span = max(iv[1] for n, ivs in signal.items() for iv in ivs) - min(iv[0] for n, ivs in signal.items() for iv in ivs)
    clusters = [[details[0]]]
    for a, b in zip(details, details[1:]):
        if distance(a['box'], b['box']) < COUPLED_WITHIN * max(a['d_ground'], b['d_ground']):
            clusters[-1].append(b)
        else:
            clusters.append([b])
    cluster_D = [max(d['box'][1] for d in c) - min(d['box'][0] for d in c) + 2 * min(d['d_ground'] for d in c)
                 for c in clusters]
    D = max(cluster_D)
    if len(clusters) > 1:
        notes.append(f"{len(details)} lines in {len(clusters)} groups of coupled lines: D = {D:.4g} is that of the largest "
                     f"group, not of the whole span {span:.4g}")

    # 5. length of the standards, from D and the guided wavelength. n_eff is estimated from the permittivities within D of
    # the lines, as the mean of the largest and the smallest: the largest alone (silicon) gave 3.45 where the study measured
    # 1.9 to 2.3 on chip, and would shorten standards that work. The solved standard's own n_eff is reported afterwards.
    eps = []
    window = (zs[0] - D, zs[1] + D)
    for dielectric in dielectrics_list.dielectrics:
        if dielectric.zmin < window[1] and dielectric.zmax > window[0]:
            material = materials_list.get_by_name(dielectric.material)
            if material is not None:
                eps.append(material.eps)
    if dielectrics_list.dielectrics:
        stack_lo = min(d.zmin for d in dielectrics_list.dielectrics)
        stack_hi = max(d.zmax for d in dielectrics_list.dielectrics)
        if window[0] < stack_lo or window[1] > stack_hi:
            eps.append(1.0)                       # the air box around the stack
    eps = eps or [1.0]
    n_est = math.sqrt((max(eps) + min(eps)) / 2)
    wavelength = C0 / (fmax * n_est) / unit
    L4, Lcap = 4 * D, wavelength / 5
    if deembedding_length:
        L, rule = float(deembedding_length), 'user'
        if L > Lcap:
            warnings.append(f"the standards' length {L:g} is more than a fifth of the guided wavelength at the highest frequency "
                            f"({Lcap:.4g}); the calibration is less accurate towards the top of the band")
        if L < 2 * D:
            warnings.append(f"the standards' length {L:g} is less than 2 D = {2 * D:.4g}; the port's field may not have settled")
    elif L4 <= Lcap:
        L, rule = L4, '4 D'
    else:
        L = max(Lcap, 2 * D)
        rule = 'wavelength / 5' if Lcap >= 2 * D else '2 D'
        notes.append(f"standards shortened from 4 D = {L4:.4g} to {L:.4g}, to stay short against the guided wavelength")
    L = round(L, 3)
    f_valid = C0 / (n_est * 5 * L * unit)
    if f_valid >= fmax * (1 - 1e-6):
        f_valid = fmax
    if f_valid < fmax * (1 - 1e-6):
        warnings.append(f"the calibration is valid up to about {f_valid / 1e9:.3g} GHz (estimate); above, it is less accurate")
    if D > wavelength / 10:
        warnings.append(f"D = {D:.4g} is more than a tenth of the guided wavelength at the highest frequency: above about "
                        f"{C0 / (n_est * 10 * D * unit) / 1e9:.3g} GHz the port is no longer a small lumped element")

    # 6. gaps
    for d in details:
        if d['u_start'] - d['depth_drawn'] > D / 10:
            raise PortWallError(f"port {d['portnumber']} on port wall {side}: the line starts {d['u_start'] - d['depth_drawn']:.4g} "
                                f"behind the port polygon, more than D/10 = {D / 10:.4g}; draw the port polygon over the line end")
        if d['gap'] < TOL:
            d['gap'] = max(round(D / 32, 3), 5 * TOL)
            d['gap_origin'] = 'tool'
        else:
            d['gap'] = round(d['gap'], 6)
            d['gap_origin'] = 'drawing'
            if d['gap'] > D / 10:
                notes.append(f"port {d['portnumber']}: the gap {d['gap']:g} is more than D/10 = {D / 10:.4g}")

    # 7. the cross-section the standards extrude: all stackup layers at the cut, via arrays as solid bars
    up = max(d['gap'] for d in details) + CUT_OFFSET
    profile = {}
    solid_vias = []
    for n, metal in metal_of.items():
        if metal.is_via:
            ivs = layers.projection(n, up, up + D, vlo, vhi)
            above = [m for k, m in conductors.items() if not m.is_via and abs(m.zmin - metal.zmax) < TOL]
            below = [m for k, m in conductors.items() if not m.is_via and abs(m.zmax - metal.zmin) < TOL]
            for neighbours in (above, below):
                if neighbours:
                    cover = _merge([iv for m in neighbours for iv in layers.cut(int(m.layernum), up, vlo, vhi)])
                    ivs = _merge([(max(a[0], b[0]), min(a[1], b[1])) for a in ivs for b in cover if _overlap(a, b)])
            if ivs:
                solid_vias.append(metal.name)
        else:
            ivs = layers.cut(n, up, vlo, vhi)
        if ivs:
            profile[n] = ivs
    if solid_vias:
        notes.append(f"vias at the cut ({', '.join(solid_vias)}) are solid bars in the standards")
    for d in details:
        for n, ivs in d['stack'].items():
            if n in profile:
                d['stack'][n] = [iv for iv in profile[n] if any(_overlap(iv, s) for s in ivs)]

    # 8. how far the cross-section stays the same: the device's distance from the wall. Compared within the port's
    # region, the lines' span widened by D on both sides (u_dev); a change farther from the lines, e.g. a slot in a
    # plane that closes or a pad frame ending, is only reported (u_far)
    plain = {n: ivs for n, ivs in profile.items() if not metal_of[n].is_via}
    s_lo = min(iv[0] for ivs in signal.values() for iv in ivs)
    s_hi = max(iv[1] for ivs in signal.values() for iv in ivs)
    wlo, whi = max(vlo, s_lo - D), min(vhi, s_hi + D)
    core = {n: _clip(ivs, wlo, whi) for n, ivs in plain.items()}
    core = {n: ivs for n, ivs in core.items() if ivs}
    scan_end = min(depth - TOL, max(2 * D, shift + D, 0.5 * (vhi - vlo) + D))
    step = max(D / 8, scan_end / 400) if scan_end > up else None
    u_dev = None
    u_far = None
    device_size = None
    # samples: a grid of D/8, and just past every polygon vertex, so that a feature narrower than the grid (a coil's
    # outer turn of 3 um next to the wall) is not stepped over; a change found at a sample began at the last vertex
    # before it, else at the previous sample
    samples, events = [], []
    if step is not None:
        k = 1
        while up + k * step <= scan_end:
            samples.append(up + k * step)
            k += 1
        events = layers.vertex_us(up, scan_end, vlo, vhi)
        samples = sorted(set(samples) | {e + 10 * TOL for e in events if e + 10 * TOL <= scan_end})

    def onset(before, at):
        return max([e for e in events if before < e < at], default=before)

    previous = up
    for u in samples:
        if u_dev is not None and u_far is not None:
            break
        here = {n: layers.cut(n, u, vlo, vhi) for n in plain}
        here = {n: ivs for n, ivs in here.items() if ivs}
        others = {n: layers.cut(n, u, vlo, vhi) for n in layers.geoms if n not in plain and not metal_of[n].is_via}
        others = {n: ivs for n, ivs in others.items() if ivs}
        if u_dev is None:
            here_core = {n: _clip(ivs, wlo, whi) for n, ivs in here.items()}
            here_core = {n: ivs for n, ivs in here_core.items() if ivs}
            if not _same_profile(here_core, core) or any(_clip(ivs, wlo, whi) for ivs in others.values()):
                u_dev = onset(previous, u)
        if u_far is None and (not _same_profile(here, plain) or others):
            u_far = onset(previous, u)
        previous = u
    if u_dev is not None:
        ground_at_wall = {}
        for n, iv in ground:
            ground_at_wall.setdefault(n, []).append(iv)
        beyond = layers.device_extent(u_dev, ground_at_wall)
        device_size = None if beyond is None else beyond[1] - beyond[0]
    far_note = None
    if u_far is not None and u_far < D / 4 and (u_dev is None or u_far < u_dev):
        # a note, not a warning: such a change outside the port's region was below the mesh noise in the study
        # (test_data/port_deembedding_study/far_change)
        far_note = (f"metal more than D = {D:.4g} away from the lines changes {u_far:.4g} from the port wall (a slot in a "
                    f"plane, a pad frame or other metal ending): the standards copy the cross-section at the wall there; "
                    f"outside the port's region this does not matter")
    # the port wall can be moved outward: the feed is extended by the wall's cross-section, the reference plane shifted
    # back to the layout edge. 'auto': until the device is at least D and half its size from the wall
    needed = 0.0
    if u_dev is not None:
        needed = max(0.0, max(D, 0.5 * device_size if device_size else 0.0) - u_dev)
    E = math.ceil(needed * 100) / 100 if extension == 'auto' else float(extension or 0.0)
    # the standards need a straight section of D/4 in front of the port: the layout's own feed, or the extension (the
    # port wall moved outward extends the feed by the wall's cross-section, so that much of it is straight by
    # construction). With the extension, metal close to the layout edge is part of the device, next to the reference
    # plane: accepted
    if u_dev is not None and u_dev + E < D / 4:
        raise PortWallError(f"the cross-section at port wall {side} changes within D/4 = {D / 4:.4g} of the wall (a line at "
                            f"an angle, a taper, or other metal close to the wall). The standards need a straight section: "
                            f"lines that cross the wall at a right angle and stay unchanged for at least D/4, or a port wall "
                            f"moved outward by at least {D / 4 - u_dev:.4g} (port_wall_extension, 'auto' finds a length)")
    if u_dev is not None:
        hint = "" if E else "; port_wall_extension = 'auto' moves the port wall away"
        if u_dev + E < D:
            notes.append(f"the device is {u_dev + E:.4g} from the port wall, less than D = {D:.4g} (a small error){hint}")
        if device_size is not None and not E and u_dev < 0.5 * device_size:
            notes.append(f"the device is {u_dev:.4g} from the port wall, less than half its size ({device_size:.4g}): the "
                         f"wall mirrors it slightly{hint}")
    if far_note:
        notes.append(far_note)
    if E:
        notes.append(f"port wall moved {E:g} outward, the reference plane back at the layout edge (exact with a ground plane "
                     f"under the lines; with ground strips that end before the device, keep the extension short)")
    if shift:
        if shift > 0 and (u_dev is not None and shift > u_dev + TOL):
            raise PortWallError(f"reference_plane_shift for {side} = {shift:g} moves the reference plane past the uniform feed, "
                                f"which ends {u_dev:.4g} from the wall")
        if shift > 0:
            notes.append(f"reference plane shifted {shift:g} into the layout: exact only if the feed is the standards' line")

    ports_order = [d['portnumber'] for d in details]
    return {
        'side': side, 'wall': wall, 'ports': ports_order,
        'port_details': [{'portnumber': d['portnumber'], 'target_layer': d['target_layer'], 'gap': d['gap'],
                          'gap_origin': d['gap_origin'], 'line': d['line'], 'converted': d['converted'],
                          'line_start': round(d['line_start'], 6),
                          'stack': [[metal_of[n].name, iv[0], iv[1]] for n, ivs in d['stack'].items() for iv in ivs]}
                         for d in details],
        'D': round(D, 6), 'span': round(span, 6), 'distance_to_ground': round(d_min, 6),
        'clusters': [{'ports': [d['portnumber'] for d in c], 'D': round(x, 6)} for c, x in zip(clusters, cluster_D)],
        'ground_layers': sorted({metal_of[n].name for n, iv in ground}),
        'eps_max': max(eps), 'n_eff_estimate': round(n_est, 4), 'L': L, 'L_rule': rule, 'valid_to_GHz': round(f_valid / 1e9, 6), 'fmax_GHz': fmax / 1e9,
        'uniform_from_wall': None if u_dev is None else round(u_dev, 6),
        'device_size': None if device_size is None else round(device_size, 6), 'shift': float(shift),
        'extension': round(E, 6), 'notes': notes,
        'transverse': [vlo, vhi],
        'profile': [[metal_of[n].name, iv[0], iv[1]] for n, ivs in profile.items() for iv in ivs],
        'warnings': warnings,
    }


def ports_on_layout_edge(allpolygons, simulation_ports):
    """{portnumber: side} for the in-plane ports whose polygon lies on exactly one side of the layout edge, the place of
    a port wall. Works without port walls: setupEM uses it to ask whether such a side should be one."""
    bxmin, bxmax, bymin, bymax = allpolygons.get_bounding_box()
    walls = {'xmin': bxmin, 'xmax': bxmax, 'ymin': bymin, 'ymax': bymax}
    polys = {}
    for poly in allpolygons.polygons:
        polys.setdefault(int(poly.layernum), []).append(poly)
    out = {}
    for port in getattr(simulation_ports, 'ports', []):
        if port.target_layername is None:
            continue
        sides = {side for poly in polys.get(int(port.source_layernum), []) for side in WALL_SIDES
                 if _local_bounds(poly, side, walls[side])[0] <= TOL}
        if len(sides) == 1:
            out[port.portnumber] = sides.pop()
    return out


def extend_walls(allpolygons, metals_list, wall_extension, boundary):
    """settings['wall_extension'] = {side: length}: the layout's cross-section at that edge continued outward by the
    length (every metal layer that reaches the edge; no vias), so that the box wall on that side sits there. For a side
    that is not a port wall. Made for the pieces of a split region: where the region has a port wall with a
    port_wall_extension, a piece without a port on that side gets the same box as the piece with the port and as the
    whole region. Changes allpolygons; returns log lines."""
    log = []
    if not wall_extension:
        return log
    if not isinstance(wall_extension, dict):
        raise PortWallError(f"wall_extension must be a dictionary per side, e.g. {{'xmin': 20.0}}, not {wall_extension!r}")
    for side in WALL_SIDES:
        if side not in wall_extension:
            continue
        E = wall_extension[side]
        if isinstance(E, bool) or not isinstance(E, (int, float)) or E < 0:
            raise PortWallError(f"wall_extension for {side} must be a length of 0 or more, not {E!r}")
        if str(boundary[BOX_SIDES.index(side)]).upper() == 'PORTWALL':
            raise PortWallError(f"wall_extension has a value for {side}, which is a port wall: use port_wall_extension there")
        if E == 0:
            continue
        bxmin, bxmax, bymin, bymax = allpolygons.get_bounding_box()
        wall = {'xmin': bxmin, 'xmax': bxmax, 'ymin': bymin, 'ymax': bymax}[side]
        vlo, vhi = (bymin, bymax) if side in ('xmin', 'xmax') else (bxmin, bxmax)
        layers = _Layers(allpolygons, metals_list, side, wall)
        done, names = set(), []
        for metal in metals_list.metals:
            number = int(metal.layernum)
            if metal.is_via or number in done:
                continue
            done.add(number)
            intervals = layers.cut(number, CUT_OFFSET, vlo, vhi)
            for v0, v1 in intervals:
                piece = _global(shapely_box(-E, v0, 0.0, v1), side, wall)
                allpolygons.add_polygon([list(c) for c in piece.exterior.coords[:-1]], number)
            if intervals:
                names.append(metal.name)
        log.append(f"Wall {side}: moved {E:g} outward, the layout edge continued with "
                   + (', '.join(names) if names else 'no metal (none reaches the edge)'))
    for side in wall_extension:
        if side not in WALL_SIDES:
            raise PortWallError(f"wall_extension has a value for {side}; it can only be xmin, xmax, ymin or ymax")
    return log


def via_ports_in_pec_walls(allpolygons, simulation_ports, dielectrics_list, boundary, margin, air_around):
    """[(portnumber, side)] of the via ports (no target layer) whose polygon lies in the plane of a PEC wall: a side with
    boundary 'PEC', no dielectric oversize and no air, so that the wall is at the layout edge. The wall shorts such a
    port. Via ports on a port wall are gap ports by now (apply_port_walls) and are not found."""
    if any(d.gdsboundary is not None for d in dielectrics_list.dielectrics):
        return []
    air = list(air_around) if isinstance(air_around, (list, tuple)) else [air_around] * 6
    bxmin, bxmax, bymin, bymax = allpolygons.get_bounding_box()
    walls = {'xmin': bxmin, 'xmax': bxmax, 'ymin': bymin, 'ymax': bymax}
    pec = [side for i, side in enumerate(WALL_SIDES)
           if str(boundary[i]).upper() == 'PEC' and margin[i] == 0 and air[i] == 0]
    if not pec:
        return []
    polys = {}
    for poly in allpolygons.polygons:
        polys.setdefault(int(poly.layernum), []).append(poly)
    out = []
    for port in getattr(simulation_ports, 'ports', []):
        if port.target_layername is not None:
            continue
        for side in pec:
            mine = polys.get(int(port.source_layernum), [])
            if mine and all(_local_bounds(poly, side, walls[side])[2] <= TOL for poly in mine):
                out.append((port.portnumber, side))
                break
    return out


def _via_port_as_gap_port(port, poly, side, wall, layers, metals_list, vrange):
    """A via port on a port wall can't stay one: its sheet would lie in the PEC wall. If one end is the line at the port
    and the other is not (a plane, or nothing), it becomes a gap port on the line's metal. Returns the line's layer name
    and a note, or raises PortWallError when it is not clear which end is the line."""
    _, pv0, _, pv1 = _local_bounds(poly, side, wall)
    if pv1 - pv0 < TOL:
        raise PortWallError(f"port {port.portnumber} is a via port drawn as a point on port wall {side}; draw it as a "
                            f"line along the edge across the line it feeds, or as an in-plane port")
    width = pv1 - pv0
    slack = max(0.25 * width, 10 * TOL)
    ends = {}
    for name in (port.from_layername, port.to_layername):
        metal = metals_list.getbylayername(name)
        if metal is None:
            raise PortWallError(f"port {port.portnumber}: layer {name} is not in the stackup")
        cut = layers.cut(int(metal.layernum), CUT_OFFSET, vrange[0], vrange[1])
        over = [iv for iv in cut if _overlap(iv, (pv0, pv1))]
        # a line: one piece of metal under the port that is not much wider than the port
        is_line = len(over) == 1 and over[0][0] >= pv0 - slack and over[0][1] <= pv1 + slack
        ends[name] = (metal, is_line)
    lines = [name for name, (metal, is_line) in ends.items() if is_line]
    if len(lines) != 1:
        which = ('both ends' if len(lines) == 2 else 'neither end') + f" ({port.from_layername}, {port.to_layername})"
        raise PortWallError(f"port {port.portnumber} is a via port on port wall {side}, and {which} is a line at the port, "
                            f"so it can't be used as a gap port. Draw an in-plane port on the line instead (target layer = "
                            f"the line's metal)")
    line = lines[0]
    other = [name for name in ends if name != line][0]
    upward = '-' not in port.direction
    line_on_top = ends[line][0].zmin >= ends[other][0].zmax - TOL
    reversed_note = '' if upward == line_on_top else '; its polarity was from the line to ground, it is now from ground to the line like every wall port'
    note = (f"port {port.portnumber}: via port {port.from_layername} -> {port.to_layername} on port wall {side}, used as a "
            f"gap port on {line}{reversed_note}")
    return line, note


def describe(result):
    """log lines for the console and setupEM"""
    lines = []
    for g in result['groups']:
        gaps = ', '.join(f"port {p['portnumber']} gap {p['gap']:g} ({'from the drawing' if p['gap_origin'] == 'drawing' else 'set by the tool'})"
                         for p in g['port_details'])
        lines.append(f"Port wall {g['side']}: ports {', '.join(str(p) for p in g['ports'])}, ground {', '.join(g['ground_layers'])}, "
                     f"D = {g['D']:.4g}, standards {g['L']:g} and {2 * g['L']:g} ({g['L_rule']}), "
                     f"valid to {g['valid_to_GHz']:.3g} GHz; {gaps}"
                     + (f"; same standards as port wall {g['shared_with']}" if g.get('shared_with') else '')
                     + (f"; port wall moved {g['extension']:g} outward, reference plane back at the layout edge"
                        if g.get('extension') else ''))
    lines.extend('Note: ' + n for n in result['notes'])
    lines.extend('WARNING: ' + w for w in result['warnings'])
    return lines


# ------------------------------------------------------------------------------------------------------- the device

def apply_port_walls(result, allpolygons, metals_list, simulation_ports):
    """Cut the gaps out of the lines (every layer of a stacked line), replace each wall port's polygon by the gap
    rectangle across the line, and point the port into the layout. Changes allpolygons and the ports in place."""
    for g in result['groups']:
        side, wall = g['side'], g['wall']
        E = g.get('extension', 0.0)
        if E:
            # the cross-section at the wall extruded outward by E: the lines from their new gap to where they start in
            # the layout (no gap is cut at the layout edge), everything else from the new wall to the layout edge
            signal = {}
            for p in g['port_details']:
                for layername, v0, v1 in p['stack']:
                    signal[(layername, v0, v1)] = p
            for layername, v0, v1 in g['profile']:
                number = int(metals_list.getbylayername(layername).layernum)
                p = signal.get((layername, v0, v1))
                u0, u1 = (-E + p['gap'], max(p.get('line_start', 0.0), 0.0)) if p else (-E, 0.0)
                piece = _global(shapely_box(u0, v0, u1, v1), side, wall)
                allpolygons.add_polygon([list(c) for c in piece.exterior.coords[:-1]], number)
        for p in g['port_details']:
            port = simulation_ports.get_port_by_number(p['portnumber'])
            if not E:
                for layername, v0, v1 in p['stack']:
                    number = int(metals_list.getbylayername(layername).layernum)
                    cutter = _global(shapely_box(-1.0, v0 - TOL / 2, p['gap'], v1 + TOL / 2), side, wall)
                    _subtract(allpolygons, number, cutter)
            allpolygons.polygons = [poly for poly in allpolygons.polygons if int(poly.layernum) != int(port.source_layernum)]
            gap_rect = _global(shapely_box(-E, p['line'][0], -E + p['gap'], p['line'][1]), side, wall)
            allpolygons.add_polygon([list(c) for c in gap_rect.exterior.coords[:-1]], int(port.source_layernum))
            if p.get('converted'):
                print(p['converted'])
                port.target_layername = p['target_layer']
                port.from_layername = port.to_layername = None
            elif port.direction.lower() != INWARD[side]:
                print(f"Port {port.portnumber} on port wall {side}: direction {INWARD[side]} (into the layout) instead of "
                      f"{port.direction}")
            port.direction = INWARD[side]


def _subtract(allpolygons, number, cutter):
    keep, added = [], []
    for poly in allpolygons.polygons:
        if int(poly.layernum) != number:
            keep.append(poly)
            continue
        shape = _shape(poly)
        if not shape.intersects(cutter) or shape.intersection(cutter).area <= TOL * TOL:
            keep.append(poly)
            continue
        rest = shape.difference(cutter)
        for piece in getattr(rest, 'geoms', [rest]):
            if piece.is_empty or piece.geom_type != 'Polygon' or piece.area <= TOL * TOL:
                continue
            if len(piece.interiors) > 0:
                raise PortWallError(f"cutting a port gap left a hole in a polygon on layer {number}")
            added.append(([[round(x, 6), round(y, 6)] for x, y in piece.exterior.coords[:-1]], poly.fill_factor))
    allpolygons.polygons = keep
    for xy, fill_factor in added:
        allpolygons.add_polygon(xy, number)
        allpolygons.polygons[-1].fill_factor = fill_factor


# ------------------------------------------------------------------------------------------------------- the standards

def standard_name(side, tag):
    return f'cal_{side}_{tag}'


def _box_of(group, margin, air, boundary):
    lo, hi = TRANSVERSE[group['side']]
    i_lo, i_hi = BOX_SIDES.index(lo), BOX_SIDES.index(hi)
    return (boundary[i_lo], boundary[i_hi], boundary[4], boundary[5], margin[i_lo], margin[i_hi], air[i_lo], air[i_hi],
            air[4], air[5])


def _same_standards(a, b, margin, air, boundary):
    """two walls whose standards would be the same: same box on the sides along the line, same layers, and positions
    within D/1000 (a thru line has the same cross-section at both ends; layout tools leave a few nm between them)"""
    if _box_of(a, margin, air, boundary) != _box_of(b, margin, air, boundary):
        return False
    tol = max(10 * TOL, min(a['D'], b['D']) / 1000)
    close = lambda x, y: abs(x - y) <= tol
    # L = 4 D: a position difference of tol in D is 4 tol in L (and more where the length cap acts)
    if not (abs(a['L'] - b['L']) <= 8 * tol and all(map(close, a['transverse'], b['transverse']))):
        return False
    if len(a['profile']) != len(b['profile']) or len(a['port_details']) != len(b['port_details']):
        return False
    for (la, a0, a1), (lb, b0, b1) in zip(a['profile'], b['profile']):
        if la != lb or not close(a0, b0) or not close(a1, b1):
            return False
    for pa, pb in zip(a['port_details'], b['port_details']):
        if pa['target_layer'] != pb['target_layer'] or not close(pa['gap'], pb['gap']):
            return False
        if not (close(pa['line'][0], pb['line'][0]) and close(pa['line'][1], pb['line'][1])):
            return False
    return True


def standard_records(result, model_basename, margin=None, air=None, boundary=None):
    """the names, files and output folders of all standards, in the order they are written and solved. With the box
    settings given, a wall whose standards would be the same as an earlier wall's uses those (shared_with)."""
    written = []
    for g in result['groups']:
        if margin is not None:
            same = next((w for w in written if _same_standards(w, g, margin, air, boundary)), None)
            if same is not None:
                g['standards'] = same['standards']
                g['shared_with'] = same['side']
                continue
            written.append(g)
        g['standards'] = []
        for tag, factor in STANDARDS:
            name = standard_name(g['side'], tag)
            g['standards'].append({'name': name, 'length': round(factor * g['L'], 6), 'config': f'config_{name}.json',
                                   'model': f'{model_basename}_{name}', 'output': f'output/{model_basename}_{name}',
                                   'key': f'{name}.key'})


def standard_model(group, factor, metals_list):
    """polygons and ports of one standard: the profile extruded along x from 0 to factor x L, the lines cut by their gaps
    at both ends; ports 1..N at x = 0 in the group's order, N+1..2N at the far end"""
    from .util_gds_reader import all_polygons_list
    from .util_simulation_setup import all_simulation_ports, simulation_port
    L = factor * group['L']
    polygons = all_polygons_list()
    signal = {}
    for p in group['port_details']:
        for layername, v0, v1 in p['stack']:
            signal[(layername, v0, v1)] = p['gap']
    for layername, v0, v1 in group['profile']:
        number = int(metals_list.getbylayername(layername).layernum)
        gap = signal.get((layername, v0, v1), 0.0)
        polygons.add_rectangle(gap, v0, L - gap, v1, number)
    ports = all_simulation_ports()
    n = len(group['port_details'])
    for j, p in enumerate(group['port_details']):
        near, far = STANDARD_PORT_LAYER + j, STANDARD_PORT_LAYER + n + j
        polygons.add_rectangle(0.0, p['line'][0], p['gap'], p['line'][1], near)
        polygons.add_rectangle(L - p['gap'], p['line'][0], L, p['line'][1], far)
        ports.add_port(simulation_port(portnumber=j + 1, voltage=1, port_Z0=50, source_layernum=near,
                                       target_layername=p['target_layer'], direction='x'))
        ports.add_port(simulation_port(portnumber=n + j + 1, voltage=1, port_Z0=50, source_layernum=far,
                                       target_layername=p['target_layer'], direction='-x'))
    vlo, vhi = group['transverse']
    polygons.set_bounding_box(0.0, L, vlo, vhi)
    return polygons, ports


def standard_settings(settings, group, record, factor, margin, air, boundary, fmax):
    """the device's settings for one standard: same stackup, mesh and solver settings, PEC walls at both ends, the
    device's box on the two sides along the line, three frequencies, written into the device's _data folder"""
    polygons, ports = standard_model(group, factor, settings['metals_list'])
    lo, hi = TRANSVERSE[group['side']]
    i_lo, i_hi = BOX_SIDES.index(lo), BOX_SIDES.index(hi)
    out = dict(settings)
    for key in ('fstart', 'fstop', 'fstep', 'fdump', 'save_gmsh_unrolled', 'preview_only'):
        out.pop(key, None)
    out.update({
        'allpolygons': polygons, 'simulation_ports': ports,
        'boundary': ['PEC', 'PEC', boundary[i_lo], boundary[i_hi], boundary[4], boundary[5]],
        'margin': [0, 0, margin[i_lo], margin[i_hi]],
        'air_around': [0, 0, air[i_lo], air[i_hi], air[4], air[5]],
        'fpoint': [fmax * x for x in STANDARD_FREQUENCY_FRACTIONS], 'adaptive_sweep': False,
        'model_basename': record['model'], 'config_suffix': '_' + record['name'],
        'no_gui': True, 'no_preview': True, '_calibration_standard': True,
    })
    return out, ports


def write_key(sim_path, record):
    """a fingerprint of the standard's mesh and config: run_sim reuses an earlier result with the same key"""
    h = hashlib.sha256()
    for filename in (record['model'] + '.msh', record['config']):
        with open(os.path.join(sim_path, filename), 'rb') as f:
            h.update(f.read())
    with open(os.path.join(sim_path, record['key']), 'w', newline='\n') as f:
        f.write(h.hexdigest() + '\n')


def port_information_record(result):
    """what combine_extend_snp.py needs, stored in port_information.json"""
    keep = ('side', 'ports', 'port_details', 'D', 'span', 'distance_to_ground', 'ground_layers', 'eps_max', 'n_eff_estimate',
            'shared_with', 'extension', 'L', 'L_rule',
            'valid_to_GHz', 'fmax_GHz', 'uniform_from_wall', 'device_size', 'shift', 'standards', 'warnings')
    return [{k: g[k] for k in keep if k in g} for g in result['groups']]


def run_script_lines(sim_path):
    """run_sim lines for the standards listed in port_information.json, before the device; an earlier result with the
    same key is reused"""
    filename = os.path.join(sim_path, 'port_information.json')
    if not os.path.isfile(filename):
        return []
    with open(filename, encoding='utf-8') as f:
        info = json.load(f)
    records = []
    for g in info.get('port_walls', []):
        for s in g.get('standards', []):
            if s['name'] not in [r['name'] for r in records]:
                records.append(s)
    lines = []
    for i, s in enumerate(records):
        out = s['output']
        lines += [f'echo "calibration standard {i + 1} of {len(records)}: {s["name"]}, 3 frequencies"',
                  f'if [ -f {out}/port-S.csv ] && cmp -s {s["key"]} {out}/cal.key; then',
                  f'  echo "  reused, solved $(cat {out}/cal.date 2>/dev/null)"',
                  'else',
                  f'  run_palace {s["config"]} && cp {s["key"]} {out}/cal.key && date > {out}/cal.date',
                  'fi']
    if records:
        lines.append('echo "device model"')
    return lines
