# Sketches of the split concept for README.md, to scale, with the dimensions read from the GDS files and assembly.xml.
#
#   python sketches.py        (after prepare_layouts.py; writes png/sketch_*.png)

import os
import xml.etree.ElementTree as ET

import gdstk
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "png")
os.makedirs(OUT, exist_ok=True)

# ---------------- data from the files ----------------
stack = ET.parse(os.path.join(HERE, "assembly.xml")).getroot()
Z = {e.get("Name"): (float(e.get("Zmin")), float(e.get("Zmax"))) for e in stack.iter() if e.get("Zmin") is not None}
Z_CUT = 39.2303                       # split_lower.xml / split_upper.xml
MIRROR_X = 780.0                      # assembly.py: interposer x' = offset_x - x


def cell(name):
    return gdstk.read_gds(os.path.join(HERE, name)).top_level()[0].polygons


die, ipo, split = cell("die_forEM.gds"), cell("interposer_forEM.gds"), cell("split_shapes.gds")


def on(polys, layer, datatype=0):
    return [p for p in polys if (p.layer, p.datatype) == (layer, datatype)]


def bbox(p):
    (x0, y0), (x1, y1) = p.bounding_box()
    return x0, y0, x1, y1


def center(p):
    x0, y0, x1, y1 = bbox(p)
    return 0.5 * (x0 + x1), 0.5 * (y0 + y1)


def mirrored(p):
    pts = np.array(p.points)
    pts[:, 0] = MIRROR_X - pts[:, 0]
    return pts


pillars = on(die, 41, 35)
PIL_W = bbox(pillars[0])[2] - bbox(pillars[0])[0]                 # octagon across flats
tubes = on(split, 205) + on(split, 206)
TUBE = bbox(tubes[0])[2] - bbox(tubes[0])[0]
SIG_X = sorted(center(p)[0] for p in tubes)                         # x of the two signal pillars
PIL_Y = sorted({round(center(p)[1], 2) for p in pillars})          # y of the G, S, G pillars
DIE_OUT = bbox(on(die, 39, 4)[0])
IPO_OUT = bbox(on(ipo, 39, 4)[0])
x0, y0, x1, y1 = IPO_OUT
IPO_OUT_M = (MIRROR_X - x1, y0, MIRROR_X - x0, y1)                  # interposer outline in the assembly
Z_TM2_TOP, Z_PIL_TOP = Z["CuPillar"]

C = dict(cu="#c8762b", tm="#e8a13c", pec="#1f4fd8", port="#d81f3a", ox="#c9d3dd", si="#8fa3b5", air="#f4f6f8",
         gap="#ffffff", out="#e9e9e9", die="#6b8e23", ipo="#7a5195", txt="#222222")


def dim_v(ax, x, z0, z1, text, side="right", fs=8, color="k", at=None):
    """vertical dimension arrow with label (at: z of the label, default the middle)"""
    ax.add_patch(FancyArrowPatch((x, z0), (x, z1), arrowstyle="<->", mutation_scale=8, lw=0.8, color=color))
    ax.text(x + (1 if side == "right" else -1) * 0.012 * np.diff(ax.get_xlim())[0], 0.5 * (z0 + z1) if at is None else at, text,
            ha="left" if side == "right" else "right", va="center", fontsize=fs, color=color)


def dim_h(ax, y, x0, x1, text, above=True, fs=8, color="k"):
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="<->", mutation_scale=8, lw=0.8, color=color))
    ax.text(0.5 * (x0 + x1), y + (1 if above else -1) * 0.012 * np.diff(ax.get_ylim())[0], text, ha="center",
            va="bottom" if above else "top", fontsize=fs, color=color)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("written png/" + name)


# =====================================================================================================
# 1. the stack of the assembly, whole height and the region between the chips
# =====================================================================================================
fig, (axa, axb) = plt.subplots(1, 2, figsize=(15, 8.5), gridspec_kw=dict(width_ratios=[1, 1.6]))

bands = [("AIR", "air below the die", C["air"]), ("Substrate", "die substrate (Si, 2 S/m)", C["si"]),
         ("EPI", "", C["si"]), ("SiO2", "die oxide (BEOL)", C["ox"]), ("Passive", "", C["ox"]),
         ("Underfill", "underfill, εr = 1 (pillars)", C["gap"]), ("iPassive", "", C["ox"]),
         ("iSiO2", "interposer oxide (BEOL)", C["ox"]), ("iSubstrate", "interposer carrier (Si, 2 S/m)", C["si"]),
         ("iAIR", "air above the interposer", C["air"])]
ax = axa
ax.set_xlim(0, 100)
ax.set_ylim(Z["AIR"][0] - 10, Z["iAIR"][1] + 10)
for name, label, color in bands:
    z0, z1 = Z[name]
    ax.add_patch(Rectangle((10, z0), 55, z1 - z0, fc=color, ec="k", lw=0.5))
    if label:
        ax.text(12, 0.5 * (z0 + z1), label, va="center", fontsize=8)
for name, xd in (("AIR", 67), ("Substrate", 67), ("iSubstrate", 67), ("iAIR", 67)):
    z0, z1 = Z[name]
    dim_v(ax, xd, z0, z1, f"{z1 - z0:g} µm")
dim_v(ax, 67, Z["EPI"][0], Z["Passive"][1], f"die BEOL {Z['Passive'][1] - Z['EPI'][0]:.2f} µm", fs=7)
dim_v(ax, 67, Z["Passive"][1], Z["iPassive"][0], "", fs=7)
ax.text(68.5, 40, f"gap {Z['iPassive'][0] - Z['Passive'][1]:.1f} µm\n(zoom on the right)", fontsize=7, va="center")
ax.add_patch(Rectangle((8, -12), 59, 100, fc="none", ec="k", lw=1, ls="--"))
ax.set_xticks([])
ax.set_ylabel("z (µm)")
ax.set_title("assembly.xml, whole height (to scale)", fontsize=10)

ax = axb
ax.set_xlim(-30, 130)
ax.set_ylim(-5, 82)
for name, label, color in bands[2:8]:
    z0, z1 = Z[name]
    ax.add_patch(Rectangle((-30, z0), 160, z1 - z0, fc=color, ec="none"))
for name, lab in (("TopMetal2", "TopMetal2 (die)"), ("iTopMetal2", "iTopMetal2 (interposer)")):
    z0, z1 = Z[name]
    ax.add_patch(Rectangle((-30, z0), 160, z1 - z0, fc=C["tm"], ec="k", lw=0.5))
    ax.text(-28, 0.5 * (z0 + z1), lab, va="center", fontsize=8)
for name in ("Metal5", "TopMetal1", "iTopMetal1", "iMetal5", "iMetal4", "Metal4"):
    z0, z1 = Z[name]
    ax.add_patch(Rectangle((60, z0), 70, z1 - z0, fc=C["tm"], ec="k", lw=0.4, alpha=0.6))
    ax.text(128, 0.5 * (z0 + z1), name, va="center", ha="right", fontsize=6.5)
ax.add_patch(Rectangle((10, Z_TM2_TOP), PIL_W, Z_PIL_TOP - Z_TM2_TOP, fc=C["cu"], ec="k", lw=0.6))
ax.text(10 + PIL_W / 2, 28, "Cu pillar", ha="center", color="w", fontsize=10)
ax.plot([-30, 130], [Z_CUT, Z_CUT], color=C["pec"], lw=1.5, ls="--")
ax.text(128, Z_CUT + 0.8, f"cut plane of the split, z = {Z_CUT:.2f}", color=C["pec"], ha="right", fontsize=8)
dim_v(ax, 56, Z_TM2_TOP, Z_PIL_TOP, f"pillar {Z_PIL_TOP - Z_TM2_TOP:g} µm", at=52)
dim_v(ax, 6, Z_TM2_TOP, Z_CUT, f"{Z_CUT - Z_TM2_TOP:g} µm", side="left")
dim_v(ax, 6, Z_CUT, Z_PIL_TOP, f"{Z_PIL_TOP - Z_CUT:g} µm", side="left")
dim_h(ax, 6, 10, 10 + PIL_W, f"{PIL_W:.1f} µm", above=False)
for z, lab in ((Z_TM2_TOP, f"{Z_TM2_TOP:.2f}"), (Z_PIL_TOP, f"{Z_PIL_TOP:.2f}"), (Z["Passive"][1], f"{Z['Passive'][1]:.2f}"),
               (Z["iPassive"][0], f"{Z['iPassive'][0]:.2f}"), (Z["iSiO2"][1], f"{Z['iSiO2'][1]:.2f}")):
    ax.plot([118, 130], [z, z], color="k", lw=0.5)
    ax.text(131, z, lab, va="center", fontsize=7)
ax.text(85, 28, "underfill (εr = 1)", fontsize=8, ha="center")
ax.text(85, 9, "die oxide", fontsize=8, ha="center")
ax.text(85, 78.5, "interposer carrier above", fontsize=8, ha="center")
ax.set_xlabel("x (µm), schematic placement")
ax.set_ylabel("z (µm)")
ax.set_title("between the chips (to scale in z); z values on the right", fontsize=10)
fig.suptitle("1  The stack: die at the bottom, interposer upside down on top, joined by copper pillars", fontsize=12)
save(fig, "sketch_1_stack.png")

# =====================================================================================================
# 2. the split concept: cross section through a GSG pillar group, assembly and the two models pulled apart
# =====================================================================================================
YS = PIL_Y
H = TUBE / 2
R = PIL_W / 2
Y0, Y1 = YS[0] - 45, YS[2] + 45
LIFT = 30          # the upper model is drawn this much higher, to show the cut


def section(ax, z_lo, z_hi, dz=0.0, gray=False):
    """oxides, metals and pillar copper between z_lo and z_hi, shifted by dz"""
    ox = C["out"] if gray else C["ox"]
    tm = "#dddddd" if gray else C["tm"]
    for name in ("SiO2", "Passive", "iPassive", "iSiO2"):
        z0, z1 = max(Z[name][0], z_lo), min(Z[name][1], z_hi)
        if z1 > z0:
            ax.add_patch(Rectangle((Y0, z0 + dz), Y1 - Y0, z1 - z0, fc=ox, ec="none"))
    for name, gaps in (("TopMetal2", (YS[0] + 30, YS[1] - 17, YS[1] + 17, YS[2] - 30)),
                       ("iTopMetal2", (YS[0] + 28, YS[1] - 23, YS[1] + 23, YS[2] - 28))):
        z0, z1 = Z[name]
        if z0 >= z_lo and z1 <= z_hi:
            edges = [Y0, *gaps, Y1]
            for a, b in zip(edges[0::2], edges[1::2]):
                ax.add_patch(Rectangle((a, z0 + dz), b - a, z1 - z0, fc=tm, ec="k" if not gray else "#bbbbbb", lw=0.5))


def copper(ax, y, z0, z1, dz=0.0, gray=False, label=None):
    ax.add_patch(Rectangle((y - R, z0 + dz), 2 * R, z1 - z0, fc="#dddddd" if gray else C["cu"],
                           ec="#bbbbbb" if gray else "k", lw=0.5))
    if label:
        ax.text(y, 0.5 * (z0 + z1) + dz, label, ha="center", va="center", color="#999999" if gray else "w",
                fontsize=12)


def tube(ax, y, z0, z1, dz=0.0):
    for yy in (y - H, y + H):
        ax.plot([yy, yy], [z0 + dz, z1 + dz], color=C["port"], lw=3)


def cut(ax, dz=0.0, label=True):
    ax.plot([Y0, Y1], [Z_CUT + dz, Z_CUT + dz], color=C["pec"], lw=3)
    if label:
        ax.text(Y1 + 3, Z_CUT + dz, "PEC cut plane", color=C["pec"], va="center", fontsize=8)


fig, axs = plt.subplots(1, 3, figsize=(21, 4.4), gridspec_kw=dict(width_ratios=[1, 1, 1]))
ax = axs[0]
section(ax, -1, 80)
for y, t in zip(YS, "GSG"):
    copper(ax, y, Z_TM2_TOP, Z_PIL_TOP, label=t)
ax.plot([Y0, Y1], [Z_CUT, Z_CUT], color=C["pec"], lw=1, ls="--")
ax.text(Y1 + 3, Z_CUT, "cut height\n(no sheet here)", color=C["pec"], va="center", fontsize=8)
ax.set_title("assembly.py: one model", fontsize=11)

ax = axs[1]
# lower model: die up to the cut
section(ax, -1, Z_CUT)
for y in (YS[0], YS[2]):
    copper(ax, y, Z_TM2_TOP, Z_CUT, label="G")
tube(ax, YS[1], Z_TM2_TOP, Z_CUT)
cut(ax)
ax.text(Y1 + 3, 8, "split_lower.py", fontsize=10, weight="bold")
# upper model: from the cut up, drawn higher
section(ax, Z_CUT, 80, dz=LIFT)
for y in (YS[0], YS[2]):
    copper(ax, y, Z_CUT, Z_PIL_TOP, dz=LIFT, label="G")
tube(ax, YS[1], Z_CUT, Z_PIL_TOP, dz=LIFT)
cut(ax, dz=LIFT)
ax.text(Y1 + 3, Z_PIL_TOP + LIFT + 6, "split_upper.py", fontsize=10, weight="bold")
for zc in (Z_CUT, Z_CUT + LIFT):
    ax.annotate("", (Y0 - 6, Z_CUT + LIFT), (Y0 - 6, Z_CUT), arrowprops=dict(arrowstyle="<->", color="#888888"))
ax.text(YS[1], Z_CUT + LIFT / 2, "the same plane in both models\n(drawn apart)", ha="center", va="center",
        fontsize=8, color="#888888")
ax.annotate("tube port (4 walls)", (YS[1] + H, 0.5 * (Z_TM2_TOP + Z_CUT)), (Y1 + 3, 26),
            color=C["port"], fontsize=8, va="center", arrowprops=dict(arrowstyle="->", color=C["port"]))
ax.annotate("tube port", (YS[1] + H, 0.5 * (Z_CUT + Z_PIL_TOP) + LIFT), (Y1 + 3, Z_CUT + LIFT + 14),
            color=C["port"], fontsize=8, va="center", arrowprops=dict(arrowstyle="->", color=C["port"]))
ax.set_title("split: two models, cut at half pillar height", fontsize=11)

ax = axs[2]
section(ax, -1, 80, gray=True)
for y, t in zip(YS, "GSG"):
    copper(ax, y, Z_TM2_TOP, Z_PIL_TOP, gray=True)
for y in (YS[0], YS[2]):
    copper(ax, y, Z_TM2_TOP, Z_CUT, label="G")
tube(ax, YS[1], Z_TM2_TOP, Z_CUT)
cut(ax)
ax.add_patch(Rectangle((Y0, Z_CUT), Y1 - Y0, 80 - Z_CUT, fc="white", ec="none", alpha=0.55))
ax.text(YS[1], 62, "not in split_lower.py", ha="center", fontsize=10, color="#666666")
dim_v(ax, YS[0] - R - 6, Z_TM2_TOP, Z_CUT, f"{Z_CUT - Z_TM2_TOP:g} µm", side="left")
dim_h(ax, 6.5, YS[1] - H, YS[1] + H, f"tube {TUBE:g} µm", above=False, color=C["port"])
dim_h(ax, Z_CUT + 3, YS[0] - R, YS[0] + R, f"{PIL_W:.1f} µm")
dim_h(ax, Z_CUT + 3, YS[1], YS[2], f"pitch {YS[2] - YS[1]:g} µm")
ax.set_title("what split_lower.py contains (the upper model is the mirror image)", fontsize=11)

for ax in axs:
    ax.set_xlim(Y0 - 12, Y1 + 75)
    ax.set_ylim(-2, 80 + (LIFT if ax is axs[1] else 0))
    ax.set_aspect("equal")
    ax.set_xlabel("y (µm), section through the left pillar group")
    ax.set_ylabel("z (µm)")
fig.suptitle("2  The split: both models end at a PEC sheet at half pillar height. Ground pillars keep their copper "
             "up to the sheet; each signal pillar is replaced by a tube port.", fontsize=12, y=0.86)
save(fig, "sketch_2_split_concept.png")

# =====================================================================================================
# 3. tube port in 3D-like view and top view
# =====================================================================================================
fig = plt.figure(figsize=(16, 6.5))
ax = fig.add_subplot(1, 2, 1, projection="3d")
sx, sy = center(tubes[0])
oct_pts = np.array(next(p for p in pillars if abs(center(p)[0] - sx) < 1 and abs(center(p)[1] - sy) < 1).points)
for z in (Z_TM2_TOP, Z_CUT):
    ring = np.vstack([oct_pts, oct_pts[:1]])
    ax.plot(ring[:, 0] - sx, ring[:, 1] - sy, z, color=C["cu"], lw=1.5, ls="--")
for px, py in oct_pts:
    ax.plot([px - sx, px - sx], [py - sy, py - sy], [Z_TM2_TOP, Z_CUT], color=C["cu"], lw=0.6, ls="--")
sq = np.array([[-H, -H], [H, -H], [H, H], [-H, H]])
for k in range(4):
    a, b = sq[k], sq[(k + 1) % 4]
    xs = [a[0], b[0], b[0], a[0]]
    ys = [a[1], b[1], b[1], a[1]]
    zs = [Z_TM2_TOP, Z_TM2_TOP, Z_CUT, Z_CUT]
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    ax.add_collection3d(Poly3DCollection([list(zip(xs, ys, zs))], fc=C["port"], ec="k", alpha=0.35, lw=0.6))
cut_sq = 40
ax.add_collection3d(Poly3DCollection([[(-cut_sq, -cut_sq, Z_CUT), (cut_sq, -cut_sq, Z_CUT), (cut_sq, cut_sq, Z_CUT),
                                       (-cut_sq, cut_sq, Z_CUT)]], fc=C["pec"], alpha=0.12, ec=C["pec"]))
ax.add_collection3d(Poly3DCollection([[(-cut_sq, -cut_sq, Z_TM2_TOP), (cut_sq, -cut_sq, Z_TM2_TOP),
                                       (cut_sq, 5, Z_TM2_TOP), (-cut_sq, 5, Z_TM2_TOP)]], fc=C["tm"], alpha=0.35))
ax.text(cut_sq, cut_sq, Z_CUT + 2, "PEC cut plane", color=C["pec"], fontsize=9)
ax.text(cut_sq, -cut_sq, Z_TM2_TOP - 3, "TopMetal2 pad", color="#9a6200", fontsize=9)
ax.text(-H, -H - 6, Z_CUT + 8, "4 port walls,\none port", color=C["port"], fontsize=9)
ax.set_xlabel("x (µm)"); ax.set_ylabel("y (µm)"); ax.set_zlabel("z (µm)")
ax.set_box_aspect((1, 1, 0.45))
ax.view_init(elev=22, azim=-58)
ax.set_title(f"tube port of split_lower.py: {TUBE:g} µm square, {Z_CUT - Z_TM2_TOP:g} µm high\n"
             "(dashed: the pillar it replaces)", fontsize=10)

ax = fig.add_subplot(1, 2, 2)
ax.add_patch(Polygon(oct_pts - [sx, sy], fc=C["cu"], ec="k", alpha=0.35, lw=0.8))
ax.add_patch(Rectangle((-H, -H), TUBE, TUBE, fc="none", ec=C["port"], lw=3))
ax.add_patch(Rectangle((-H, -H), TUBE, TUBE, fc=C["port"], alpha=0.08))
dim_h(ax, -R - 4, -R, R, f"pillar {PIL_W:.1f} µm (octagon, across flats)", above=False)
dim_h(ax, H + 3, -H, H, f"{TUBE:g} µm", color=C["port"])
dim_v(ax, H + 4, -H, H, f"{TUBE:g} µm", color=C["port"])
ax.text(0, -3, "drawn on GDS 205\n(one square = one port)", ha="center", fontsize=8, color=C["port"])
ax.text(0, R + 6, f"the corners of the square stay inside the octagon:\nsquare diagonal {TUBE * 2 ** 0.5:.1f} µm "
        f"< {PIL_W:.1f} µm across flats", ha="center", fontsize=8)
ax.set_xlim(-R - 12, R + 30); ax.set_ylim(-R - 14, R + 16); ax.set_aspect("equal")
ax.set_xlabel("x (µm)"); ax.set_ylabel("y (µm)")
ax.set_title("top view of the signal pillar", fontsize=10)
fig.suptitle("3  The tube port: a square on the port layer becomes four vertical walls, as one port", fontsize=12)
save(fig, "sketch_3_tube_port.png")

# =====================================================================================================
# 4. top view of the assembly: die on the mirrored interposer, ports and pillars
# =====================================================================================================
fig, ax = plt.subplots(figsize=(17, 5.4))
ax.add_patch(Rectangle(IPO_OUT_M[:2], IPO_OUT_M[2] - IPO_OUT_M[0], IPO_OUT_M[3] - IPO_OUT_M[1], fc=C["ipo"],
                       alpha=0.08, ec=C["ipo"], lw=1.5))
ax.add_patch(Rectangle(DIE_OUT[:2], DIE_OUT[2] - DIE_OUT[0], DIE_OUT[3] - DIE_OUT[1], fc=C["pec"], alpha=0.10,
                       ec=C["die"], lw=2))
for p in on(ipo, 134):
    ax.add_patch(Polygon(mirrored(p), fc=C["tm"], ec="k", lw=0.3, alpha=0.55))
for p in on(die, 134):
    ax.add_patch(Polygon(p.points, fc="#b35900", ec="k", lw=0.3, alpha=0.7))
for p in pillars:
    ax.add_patch(Polygon(p.points, fc="none", ec=C["cu"], lw=1.5))
for p, n in zip(sorted(tubes, key=lambda p: center(p)[0]), (5, 6)):
    x0, y0, x1, y1 = bbox(p)
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec=C["port"], lw=2))
    ax.text(x1 + 4, 140, f"tube port {n}\n(lower model: {n - 4})", color=C["port"], fontsize=8, va="bottom")
for p in ipo:
    if 201 <= p.layer <= 204:
        pts = mirrored(p)
        ax.add_patch(Polygon(pts, fc=C["port"], ec=C["port"]))
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        ax.text(cx, cy + (22 if cy > 110 else -22), f"{p.layer - 200}", color=C["port"], ha="center", va="center",
                fontsize=11, weight="bold")
ax.text(DIE_OUT[0] + 5, DIE_OUT[3] - 5, "die (and PEC cut plane in the split)", color=C["die"], fontsize=9,
        va="top")
ax.text(IPO_OUT_M[0] + 5, IPO_OUT_M[3] - 5, "interposer (mirrored: x' = 780 - x)", color=C["ipo"], fontsize=9,
        va="top")
dim_h(ax, DIE_OUT[1] - 25, DIE_OUT[0], DIE_OUT[2], f"die {DIE_OUT[2] - DIE_OUT[0]:g} µm", above=False)
dim_h(ax, IPO_OUT_M[3] + 30, IPO_OUT_M[0], IPO_OUT_M[2], f"interposer {IPO_OUT_M[2] - IPO_OUT_M[0]:g} µm")
dim_h(ax, 240, SIG_X[0], SIG_X[1], f"{SIG_X[1] - SIG_X[0]:.0f} µm between the signal pillars")
dim_v(ax, DIE_OUT[2] + 8, DIE_OUT[1], DIE_OUT[3], f"{DIE_OUT[3] - DIE_OUT[1]:g} µm", at=250)
ax.text(0.5 * (SIG_X[0] + SIG_X[1]), 120, "line on the die (TopMetal2, 9.4 µm)", ha="center", fontsize=8)
ax.text(-140, 120, "line on the interposer", ha="center", fontsize=8)
ax.text(600, 120, "line on the interposer", ha="center", fontsize=8)
ax.annotate("", (SIG_X[0], -40), (-310, -40), arrowprops=dict(arrowstyle="->", color="#555555", lw=1.2))
ax.annotate("", (SIG_X[1], -40), (SIG_X[0], -40), arrowprops=dict(arrowstyle="->", color="#555555", lw=1.2))
ax.annotate("", (740, -40), (SIG_X[1], -40), arrowprops=dict(arrowstyle="->", color="#555555", lw=1.2))
ax.text(215, -50, "signal path: probe ports 3, 4 → interposer → pillar → die → pillar → interposer → probe ports 1, 2",
        ha="center", va="top", fontsize=8, color="#555555")
ax.set_xlim(IPO_OUT_M[0] - 20, IPO_OUT_M[2] + 60); ax.set_ylim(DIE_OUT[1] - 60, IPO_OUT_M[3] + 60)
ax.set_aspect("equal"); ax.set_xlabel("x (µm), die coordinates"); ax.set_ylabel("y (µm)")
fig.suptitle("4  Top view of the assembly: the die (green outline) lies on the interposer; 4 probe ports, "
             "2 signal pillars with tube ports, 4 ground pillars", fontsize=12)
save(fig, "sketch_4_top_view.png")

# =====================================================================================================
# 5. probe port detail on the interposer
# =====================================================================================================
fig, ax = plt.subplots(figsize=(8, 8))
CXP = 40.0
for p in on(ipo, 134):
    x0, y0, x1, y1 = bbox(p)
    if x1 > CXP - 40 and x0 < CXP + 40:
        ax.add_patch(Polygon(p.points, fc=C["tm"], ec="k", lw=0.6, alpha=0.8))
for p in ipo:
    if p.layer in (201, 202):
        x0, y0, x1, y1 = bbox(p)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=C["port"], alpha=0.35, ec=C["port"], lw=2))
        ax.text(x1 + 2, 0.5 * (y0 + y1), f"port {p.layer - 200} (GDS {p.layer})\n{x1 - x0:g} × {y1 - y0:.1f} µm,\n"
                f"direction {'y' if p.layer == 201 else '-y'}", fontsize=8, va="center", color=C["port"])
        ax.add_patch(FancyArrowPatch((CXP, y0 + 3 if p.layer == 201 else y1 - 3),
                                     (CXP, y1 - 3 if p.layer == 201 else y0 + 3), arrowstyle="->",
                                     mutation_scale=12, color=C["port"], lw=1.5))
        dim_h(ax, y0 - 2 if p.layer == 202 else y1 + 2, x0, x1, f"{x1 - x0:g} µm", above=p.layer == 201,
              color=C["port"])
for yl in (132.935 - 8, 87.065):
    ax.add_patch(Rectangle((CXP - 10, yl), 20, 8, fc="none", ec="k", lw=1, hatch="///"))
ax.annotate("port landing: 20 × 8 µm TopMetal2,\ngives the round pad a straight edge", (CXP + 10, 129),
            (CXP + 26, 118), fontsize=8, arrowprops=dict(arrowstyle="->"))
ax.text(CXP, 110, "S", ha="center", va="center", fontsize=16)
ax.text(CXP, 185, "G", ha="center", va="center", fontsize=16)
ax.text(CXP, 35, "G", ha="center", va="center", fontsize=16)
ax.set_xlim(CXP - 40, CXP + 80); ax.set_ylim(0, 220); ax.set_aspect("equal")
ax.set_xlabel("x (µm), interposer coordinates"); ax.set_ylabel("y (µm)")
ax.set_title("5  Probe ports at one end of the interposer (interposer_forEM.gds):\n"
             "from the signal pad to the ground pad above and below", fontsize=11)
save(fig, "sketch_5_probe_ports.png")

# =====================================================================================================
# 6. ports and join
# =====================================================================================================
fig, ax = plt.subplots(figsize=(14, 6.5))
ax.set_xlim(0, 140); ax.set_ylim(0, 65); ax.axis("off")


def box(x, y, w, h, title, color):
    ax.add_patch(Rectangle((x, y), w, h, fc=color, alpha=0.12, ec=color, lw=2))
    ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=11, weight="bold", color=color)


def pin(x, y, label, side):
    dx = {"left": -6, "right": 6, "up": 0, "down": 0}[side]
    dy = {"left": 0, "right": 0, "up": 5, "down": -5}[side]
    ax.plot([x, x + dx], [y, y + dy], color="k", lw=1.2)
    ax.plot(x + dx, y + dy, "o", color="k", ms=4)
    ax.text(x + dx * 1.35 + (0 if dx else 2.5), y + dy * 1.35, label, ha="center", va="center", fontsize=9)


box(10, 38, 50, 16, "split_upper\n6-port (interposer)", C["ipo"])
pin(10, 50, "1", "left"); pin(10, 42, "2", "left"); pin(60, 50, "3", "right"); pin(60, 42, "4", "right")
pin(25, 38, "5", "down"); pin(45, 38, "6", "down")
box(10, 8, 50, 14, "split_lower\n2-port (die)", C["die"])
pin(25, 22, "1", "up"); pin(45, 22, "2", "up")
for xx, txt in ((25, "upper 5 ↔ lower 1\nleft signal pillar"), (45, "upper 6 ↔ lower 2\nright signal pillar")):
    ax.plot([xx, xx], [27, 33], color=C["port"], lw=2.5)
    ax.text(xx + 4.5, 30, txt, fontsize=8, va="center", color=C["port"])
ax.text(35, 3.5, "join_split.py: rf.network.connect(upper, 4, lower, 0), then innerconnect(…, 4, 5)",
        ha="center", fontsize=8.5, family="monospace")
ax.annotate("", (88, 31), (70, 31), arrowprops=dict(arrowstyle="-|>", lw=2, color="#555555"))
box(92, 23, 36, 16, "joined 4-port\n= assembly.py", "#333333")
pin(92, 35, "1", "left"); pin(92, 27, "2", "left"); pin(128, 35, "3", "right"); pin(128, 27, "4", "right")
ax.text(110, 15, "compared with the 4 probe ports\nof the one-model reference", ha="center", fontsize=9)
ax.text(35, 60, "tube ports: lower model direction 'z' (up to the cut plane), upper model '-z' (down to it)\n"
        "→ the same polarity at the cut, so the ports can be connected directly", ha="center", fontsize=9)
fig.suptitle("6  Ports and join: the tube ports of the two models are connected pillar by pillar", fontsize=12)
save(fig, "sketch_6_join.png")
