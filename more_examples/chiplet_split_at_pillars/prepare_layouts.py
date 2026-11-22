# Prepares the layouts of this example from the public OpenIntM4TM2 example layouts
# (https://github.com/IHP-GmbH/OpenIntM4TM2, Apache License 2.0).
#
#   python prepare_layouts.py
#
# Downloads T591_BEOL_D1_300u.gds (die) and T591_BEOL_I1_2x300u.gds (interposer) into public_layouts/
# if they are not there yet, and writes:
#   die_forEM.gds          the die, simplified for EM
#   interposer_forEM.gds   the interposer, simplified for EM, with the four probe ports (GDS 201-204)
#   split_shapes.gds       the shapes for the split models, in die coordinates: cut sheet (GDS 220),
#                          ground pillars (GDS 221) and one square per signal pillar for the tube ports (GDS 205, 206)
#
# Changes to the public layouts:
#   - gds_prepare_for_EM: fill removed, small holes in ground planes filled, via arrays merged (5 um),
#     round shapes such as the pillar pads turned into octagons
#   - TopVia2 pieces that gds_prepare_for_EM left in each interposer pad joined into one block (10 um gap)
#   - curves (round pads, merged via blocks) approximated with fewer vertices, within 0.5 um: the round shapes of
#     the public layouts have up to 500 vertices, which makes the gmsh geometry step take many minutes
#   - only the layers of the stackup kept, plus the chip outline (39/4) for the dielectric boundary
#   - interposer: a small TopMetal2 rectangle at each probe port, so that the round signal pad has a straight
#     edge for the port ("port landing")

import os
import subprocess
import sys
import tempfile
import urllib.request

import gdstk
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = "v2026.11.4"
URL = f"https://raw.githubusercontent.com/IHP-GmbH/OpenIntM4TM2/{TAG}/libs.ref/intm4tm2_examples/gds/"
DIE_SRC = "T591_BEOL_D1_300u.gds"
INTERPOSER_SRC = "T591_BEOL_I1_2x300u.gds"

METALS_AND_VIAS = (50, 66, 67, 125, 126, 133, 134)   # Metal4 ... TopMetal2: all the die and interposer use
PILLAR = (41, 35)          # die: copper pillar pad opening = pillar footprint
OUTLINE = (39, 4)          # chip outline, used as dielectric boundary
TOPVIA2, TOPMETAL2 = 133, 134

L_CUT, L_GND_PILLARS = 220, 221       # split_shapes.gds
L_TUBE = (205, 206)                   # tube ports, left and right signal pillar
TUBE = 29.0                           # side of the tube port square: fits on the pillar's octagonal end face


def download(name):
    path = os.path.join(HERE, "public_layouts", name)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("downloading", URL + name)
        urllib.request.urlretrieve(URL + name, path)
    return path


def prepare(src):
    """gds_prepare_for_EM with 5 um via merging; returns the polygons of the design cell"""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "prepared.gds")
        subprocess.run(["gds_prepare_for_EM", "--via-merge-size", "5", src, out], check=True,
                       stdout=subprocess.DEVNULL)
        return gdstk.read_gds(out).top_level()[0].get_polygons()


def outline(src):
    polys = [p for p in gdstk.read_gds(src).top_level()[0].get_polygons() if (p.layer, p.datatype) == OUTLINE]
    assert len(polys) == 1, "expected one chip outline on 39/4"
    return polys[0]


def keep(polys, extra=()):
    return [p for p in polys if (p.datatype == 0 and p.layer in METALS_AND_VIAS) or (p.layer, p.datatype) in extra]


def join_pieces(polys, layer, gap=10.0):
    """join pieces on one layer that are closer than gap (one block per pad)"""
    others = [p for p in polys if (p.layer, p.datatype) != (layer, 0)]
    pieces = [p for p in polys if (p.layer, p.datatype) == (layer, 0)]
    grown = gdstk.offset(pieces, gap / 2, join="miter", layer=layer, datatype=0)
    return others + gdstk.offset(grown, -gap / 2, join="miter", layer=layer, datatype=0)


def _rdp(points, tol):
    """Ramer-Douglas-Peucker: drop the points of an open polyline that are closer than tol to the simplified line"""
    a, b = points[0], points[-1]
    d = b - a
    norm = np.hypot(*d)
    rel = points - a
    dist = np.abs(d[0] * rel[:, 1] - d[1] * rel[:, 0]) / norm if norm > 0 else np.hypot(rel[:, 0], rel[:, 1])
    k = int(np.argmax(dist))
    if dist[k] <= tol:
        return np.array([a, b])
    return np.vstack([_rdp(points[:k + 1], tol)[:-1], _rdp(points[k:], tol)])


def fewer_vertices(polys, tol=0.5):
    """approximate curves (round pads, merged via blocks) with fewer vertices, within tol (um)"""
    out = []
    for p in polys:
        pts = np.array(p.points)
        if len(pts) <= 8:
            out.append(p)
            continue
        far = int(np.argmax(np.hypot(*(pts - pts[0]).T)))          # split the closed ring into two polylines
        ring = np.vstack([pts, pts[:1]])
        simple = np.vstack([_rdp(ring[:far + 1], tol)[:-1], _rdp(ring[far:], tol)[:-1]])
        out.append(gdstk.Polygon(simple, layer=p.layer, datatype=p.datatype))
    return out


def write(name, cellname, polys):
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.new_cell(cellname).add(*polys)
    lib.write_gds(os.path.join(HERE, name), max_points=8190)    # default 199 would split round shapes
    print("written", name)


def rect(x0, y0, x1, y1, layer):
    return gdstk.rectangle((x0, y0), (x1, y1), layer=layer, datatype=0)


def center(p):
    (x0, y0), (x1, y1) = p.bounding_box()
    return 0.5 * (x0 + x1), 0.5 * (y0 + y1)


# ---------------- die ----------------
die_src = download(DIE_SRC)
die = fewer_vertices(keep(prepare(die_src), extra=[PILLAR])) + [outline(die_src)]
write("die_forEM.gds", "die_forEM", die)

# ---------------- interposer ----------------
ipo_src = download(INTERPOSER_SRC)
ipo = fewer_vertices(join_pieces(keep(prepare(ipo_src)), TOPVIA2)) + [outline(ipo_src)]

# Probe ports at both ends of the interposer: the signal pad is round (radius R, center (cx, 110)), the ground
# pads above and below are octagons with a flat edge facing it. Port = gap between them, 20 um wide.
R, W = 22.935, 20.0
tm2 = [p for p in ipo if (p.layer, p.datatype) == (TOPMETAL2, 0)]
for k, cx in enumerate((40.0, 1090.0)):
    gnd = sorted((p for p in tm2 if len(p.points) == 8 and abs(center(p)[0] - cx) < 1), key=lambda p: center(p)[1])
    assert len(gnd) == 2, f"ground pads at x = {cx} not found"
    y_gnd_low, y_gnd_high = gnd[0].bounding_box()[1][1], gnd[1].bounding_box()[0][1]
    y_sig_low, y_sig_high = 110 - R, 110 + R
    ipo.append(rect(cx - W / 2, y_sig_high - 8, cx + W / 2, y_sig_high, TOPMETAL2))      # port landings
    ipo.append(rect(cx - W / 2, y_sig_low, cx + W / 2, y_sig_low + 8, TOPMETAL2))
    ipo.append(rect(cx - W / 2, y_sig_high, cx + W / 2, y_gnd_high, 201 + 2 * k))         # port: signal -> ground above
    ipo.append(rect(cx - W / 2, y_gnd_low, cx + W / 2, y_sig_low, 202 + 2 * k))           # port: signal -> ground below
write("interposer_forEM.gds", "interposer_forEM", ipo)

# ---------------- shapes for the split models ----------------
pillars = [p for p in die if (p.layer, p.datatype) == PILLAR]
y_signal = sorted({round(center(p)[1], 2) for p in pillars})[1]
signal = sorted((p for p in pillars if abs(center(p)[1] - y_signal) < 1), key=lambda p: center(p)[0])
ground = [p for p in pillars if abs(center(p)[1] - y_signal) >= 1]
assert len(signal) == 2 and len(ground) == 4

(x0, y0), (x1, y1) = outline(die_src).bounding_box()
split = [rect(x0, y0, x1, y1, L_CUT)]                                                     # cut sheet: die outline
split += [gdstk.Polygon(p.points, layer=L_GND_PILLARS, datatype=0) for p in ground]       # ground pillars
for p, layer in zip(signal, L_TUBE):                                                      # tube ports
    cx, cy = center(p)
    split.append(rect(cx - TUBE / 2, cy - TUBE / 2, cx + TUBE / 2, cy + TUBE / 2, layer))
write("split_shapes.gds", "split_shapes", split)
