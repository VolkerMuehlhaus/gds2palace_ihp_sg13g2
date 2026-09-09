#!/usr/bin/env python
"""Render the ind_frame spiral inductor layout with port 1/2 positions labeled.

Reuses gds_viewer's exact rendering path (same IHP SG13G2 colors/dither
patterns) and overlays markers at the via-port locations (GDS layers
201/202 -- the source_layernum values used in the palace_ind_frame*.py
model scripts). Port coordinates are read from a generated
port_information.json (falls back to a hardcoded default measured directly
from the GDS if no run has been generated yet).
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
GDS_FILE = os.path.join(STUDY_DIR, "ind_frame_with_ports.gds")
OUT_FILE = os.path.join(HERE, "plots", "ind_frame_layout_labeled.png")

PORT_NAMES = {1: "Port 1", 2: "Port 2"}

# fallback coordinates, measured directly from the GDS (layers 201/202) if no
# port_information.json is available yet
FALLBACK_CENTROIDS = {1: (60.0, -1.5), 2: (60.0, 130.5)}


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
    fig_height = max(4.0, min(20.0, fig_width * height / width))
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
    marker_r = span * 0.012
    for port_num, (cx, cy) in centroids.items():
        ax.plot(cx, cy, marker='o', markersize=marker_r * 6, markerfacecolor='none',
                markeredgecolor='#ffffff', markeredgewidth=1.6, zorder=10)
        dx = 1 if cx >= (x0 + x1) / 2 else -1
        dy = 1 if cy >= (y0 + y1) / 2 else -1
        ax.annotate(
            PORT_NAMES[port_num],
            xy=(cx, cy),
            xytext=(cx + dx * span * 0.14, cy + dy * span * 0.10),
            color="#ffffff", fontsize=13, fontweight='bold', zorder=11,
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#ffffff', lw=1.2),
            bbox=dict(boxstyle='round,pad=0.25', fc='#000000', ec='#ffffff', lw=0.8, alpha=0.75),
        )

    margin = span * 0.15
    ax.set_xlim(x0 - margin, x1 + margin)
    ax.set_ylim(y0 - margin, y1 + margin)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(OUT_FILE, facecolor=background, dpi=dpi)
    plt.close(fig)
    print(f"Saved labeled layout to {OUT_FILE}")
    print("Port centroids (um):", centroids)


if __name__ == "__main__":
    main()
