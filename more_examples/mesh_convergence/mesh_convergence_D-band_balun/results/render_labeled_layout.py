#!/usr/bin/env python
"""Render the balun layout with port 1/2/3 positions labeled.

Reuses gds_viewer's exact rendering path (same IHP SG13G2 colors/dither
patterns) and overlays markers at the via-port locations (GDS layers 201,
202, 203 -- the source_layernum values used in the palace_balun_mesh*.py
model scripts), so port numbering matches the port list in the models.
"""
import os
import sys

sys.path.insert(0, r"D:\github-claude\gds_viewer")
import gdspy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch

import gds_viewer as gv

HERE = os.path.dirname(os.path.abspath(__file__))
GDS_FILE = os.path.join(os.path.dirname(HERE), "Balun_140-170G_RupokDas_with_ports.gds")
OUT_FILE = os.path.join(HERE, "plots", "balun_layout_labeled.png")

# port number -> GDS layer (source_layernum in the model scripts)
PORT_LAYERS = {1: 201, 2: 202, 3: 203}


def port_centroids(cell):
    polys = cell.get_polygons(by_spec=True)
    centroids = {}
    for port_num, layer in PORT_LAYERS.items():
        plist = polys.get((layer, 0), [])
        if not plist:
            continue
        verts = plist[0]
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        centroids[port_num] = (cx, cy)
    return centroids


def main():
    lib = gdspy.GdsLibrary(infile=GDS_FILE)
    cell = gv.pick_cell(lib, None)
    centroids = port_centroids(cell)

    background = "#000000"
    polygons_by_spec = cell.get_polygons(by_spec=True, depth=gv.FULL_DEPTH)
    (x0, y0), (x1, y1) = cell.get_bounding_box()
    width, height = x1 - x0, y1 - y0
    fig_width = 12.0
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

        import numpy as np
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

    # --- port markers + labels, added on top of the accurate layer rendering ---
    span = max(width, height)
    marker_r = span * 0.012
    for port_num, (cx, cy) in centroids.items():
        ax.plot(cx, cy, marker='o', markersize=marker_r * 6, markerfacecolor='none',
                markeredgecolor='#ffffff', markeredgewidth=1.6, zorder=10)
        # offset label away from the design center so text doesn't overlap the port
        dx = 1 if cx >= 0 else -1
        dy = 1 if cy >= 0 else -1
        ax.annotate(
            f"Port {port_num}",
            xy=(cx, cy),
            xytext=(cx + dx * span * 0.06, cy + dy * span * 0.06),
            color="#ffffff", fontsize=13, fontweight='bold', zorder=11,
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#ffffff', lw=1.2),
            bbox=dict(boxstyle='round,pad=0.25', fc='#000000', ec='#ffffff', lw=0.8, alpha=0.75),
        )

    margin = span * 0.10
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
