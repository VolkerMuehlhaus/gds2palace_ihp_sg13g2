#!/usr/bin/env python
"""Render the trans_100diff_to_80se_ports MIM-loaded balun layout with port
positions and MIM capacitor nominal values labeled.

Reuses gds_viewer's exact rendering path (same IHP SG13G2 colors/dither
patterns) and overlays:
  - port markers at the via-port locations (GDS layers 201/202/203 --
    201 = single-ended port 1 (target 80 ohm external), 202/203 =
    differential pair ports 2/3 (target 100 ohm external differential)).
    Port coordinates are read from a generated port_information.json
    (falls back to a hardcoded default measured directly from the GDS).
  - MIM capacitor value labels, read from the GDS text layer (63/0) inside
    the "cmim_CDNS_*" library sub-cells. gdspy does not reliably flatten
    text labels out of nested cell references across this layout's 13-cell
    hierarchy, so these were extracted once via a KLayout RBA
    RecursiveShapeIterator (both the polygon-layer 36/0 MIM plate centers
    and the text positions correctly composed through the full transform
    chain, cross-checked against each other) and are hardcoded below --
    regenerate them the same way if the GDS changes.
"""
import os
import sys
import json
import glob

sys.path.insert(0, r"D:\github-claude\gds_viewer")
import gdspy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import numpy as np

import gds_viewer as gv

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR = os.path.dirname(HERE)
GDS_FILE = os.path.join(STUDY_DIR, "trans_100diff_to_80se_ports.gds")
OUT_FILE = os.path.join(HERE, "plots", "trans_100diff_to_80se_ports_layout_labeled.png")

PORT_NAMES = {1: "P1 (SE, 80\u03a9)", 2: "P2 (diff+, 100\u03a9)", 3: "P3 (diff-, 100\u03a9)"}

# fallback port coordinates, measured directly from the GDS (layers 201-203)
FALLBACK_CENTROIDS = {1: (-35.0, 3.5), 2: (315.0, -12.0), 3: (315.0, -22.0)}

# MIM capacitor labels: (x, y, value string), measured directly from the GDS
# text layer 63/0 (cross-checked against the MIM plate polygon centers on
# layer 36/0 -- see module docstring)
MIM_LABELS = [
    (4.8, -46.4, "280.026 fF"),
    (288.28, -37.5, "349.908 fF"),
    (288.28, 3.5, "349.908 fF"),
]


def find_port_centroids():
    candidates = sorted(glob.glob(os.path.join(STUDY_DIR, "palace_model", "*_data", "port_information.json")))
    for path in candidates:
        try:
            with open(path) as f:
                info = json.load(f)
            centroids = {}
            for p in info["ports"]:
                cx = (p["xmin"] + p["xmax"]) / 2.0
                cy = (p["ymin"] + p["ymax"]) / 2.0
                centroids[p["portnumber"]] = (cx, cy)
            if centroids:
                print(f"Using port coordinates from {path}")
                return centroids
        except Exception:
            continue
    print("No port_information.json found yet, using fallback coordinates measured from GDS")
    return FALLBACK_CENTROIDS


def main():
    centroids = find_port_centroids()

    lib = gdspy.GdsLibrary(infile=GDS_FILE)
    cell = gv.pick_cell(lib, None)

    background = "#000000"
    polygons_by_spec = cell.get_polygons(by_spec=True, depth=gv.FULL_DEPTH)
    (x0, y0), (x1, y1) = cell.get_bounding_box()
    width, height = x1 - x0, y1 - y0
    fig_width = 10.0
    fig_height = max(4.0, min(24.0, fig_width * height / width))
    dpi = 200

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor=background)
    ax.set_facecolor(background)

    px_per_um = (fig_width * dpi) / width

    ordered_keys = [k for k in gv.LAYER_STYLES if k in polygons_by_spec]
    ordered_keys += [k for k in polygons_by_spec if k not in gv.LAYER_STYLES]

    for key in ordered_keys:
        if key[1] in gv.HIDDEN_DATATYPES:
            continue
        polygons = polygons_by_spec[key]
        color, pattern_name = gv.LAYER_STYLES.get(key, (gv.DEFAULT_COLOR, gv.DEFAULT_PATTERN))
        compound_path = Path.make_compound_path(*(Path(p) for p in polygons))

        tile_rows = gv.PATTERN_TILES.get(pattern_name) if pattern_name else None
        if pattern_name is not None and tile_rows is None and pattern_name in gv.PATTERN_TILES:
            ax.add_patch(PathPatch(compound_path, facecolor="none", edgecolor=color,
                                    linewidth=gv.OUTLINE_LINEWIDTH, linestyle="solid"))
            continue

        if tile_rows is None:
            ax.add_patch(PathPatch(compound_path, facecolor=color, edgecolor=color,
                                    linewidth=gv.OUTLINE_LINEWIDTH, linestyle="solid"))
            continue

        tile = np.array([[c == "*" for c in row] for row in tile_rows], dtype=bool)
        th, tw = tile.shape
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        rgba_tile = np.zeros((th, tw, 4), dtype=np.uint8)
        rgba_tile[tile] = (*rgb, 255)

        verts = compound_path.vertices
        bx0, by0 = verts.min(axis=0)
        bx1, by1 = verts.max(axis=0)
        out_w = max(1, int((bx1 - bx0) * px_per_um))
        out_h = max(1, int((by1 - by0) * px_per_um))
        reps_x = out_w // tw + 2
        reps_y = out_h // th + 2
        big = np.tile(rgba_tile, (reps_y, reps_x, 1))[:out_h, :out_w]

        im = ax.imshow(big, extent=(bx0, bx0 + out_w / px_per_um, by0, by0 + out_h / px_per_um),
                        origin="upper", interpolation="nearest")
        im.set_clip_path(PathPatch(compound_path, transform=ax.transData))
        ax.add_patch(PathPatch(compound_path, facecolor="none", edgecolor=color,
                                linewidth=gv.OUTLINE_LINEWIDTH, linestyle="solid"))

    # --- port markers + labels ---
    span = max(width, height)
    marker_r = span * 0.008
    for port_num, (cx, cy) in centroids.items():
        ax.plot(cx, cy, marker='o', markersize=marker_r * 6, markerfacecolor='none',
                markeredgecolor='#ffffff', markeredgewidth=1.6, zorder=10)
        dx = 1 if cx >= (x0 + x1) / 2 else -1
        dy = 1 if cy >= (y0 + y1) / 2 else -1
        ax.annotate(
            PORT_NAMES[port_num],
            xy=(cx, cy),
            xytext=(cx + dx * span * 0.14, cy + dy * span * 0.06),
            color="#ffffff", fontsize=11, fontweight='bold', zorder=11,
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#ffffff', lw=1.2),
            bbox=dict(boxstyle='round,pad=0.25', fc='#000000', ec='#ffffff', lw=0.8, alpha=0.75),
        )

    # --- MIM capacitor value labels ---
    for cx, cy, value in MIM_LABELS:
        ax.plot(cx, cy, marker='s', markersize=marker_r * 5, markerfacecolor='none',
                markeredgecolor='#ffff00', markeredgewidth=1.4, zorder=10)
        ax.annotate(
            value,
            xy=(cx, cy),
            xytext=(cx, cy - span * 0.045),
            color="#ffff00", fontsize=10, fontweight='bold', zorder=11,
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#ffff00', lw=1.0),
            bbox=dict(boxstyle='round,pad=0.2', fc='#000000', ec='#ffff00', lw=0.8, alpha=0.8),
        )

    margin = span * 0.08
    ax.set_xlim(x0 - margin, x1 + margin)
    ax.set_ylim(y0 - margin, y1 + margin)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(OUT_FILE, facecolor=background, dpi=dpi)
    plt.close(fig)
    print(f"Saved labeled layout to {OUT_FILE}")
    print("Port centroids (um):", centroids)
    print("MIM cap labels (um, value):", MIM_LABELS)


if __name__ == "__main__":
    main()
