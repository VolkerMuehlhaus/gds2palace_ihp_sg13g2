"""Figures of the frame margin study, written to plots/."""
import io
import os

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np

import analyze
import study

HERE =os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID, SURFACE = "#1f1f1e", "#6b6b68", "#e6e6e3", "#fcfcfb"
MARGIN_COLOR = {30: "#104281", 50: "#256abf", 100: "#5598e7", 150: "#9ec5f4"}   # dark = close to the coil
COILS = [("L0n5", "0.5 nH coil (D = 87.1 µm)", 40.0, (0.46, 0.70)), ("L2n0", "2 nH coil (D = 147.7 µm)", 15.0, (1.9, 3.4))]

plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})


def curves(name):
    f, y = analyze.read_y(name)
    return f, analyze.values(f, y)


def finish(fig, axes, legend_axis, title, out):
    for ax in axes.flat:
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, lw=0.8, which="major")
        ax.set_axisbelow(True)
    handles, labels = legend_axis.get_legend_handles_labels()
    fig.legend(handles, labels, title=title, loc="upper center", ncol=len(labels) if len(labels) < 6 else 4,
               frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    path = os.path.join(HERE, "plots", out)
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path)


def series_figure(runs, title, out, limits=True):
    """L and Q against frequency, one column per coil. runs: (suffix, label, color, line style)."""
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7), sharex="col", facecolor=SURFACE)
    for column, (coil, coil_title, f_max, l_limits) in enumerate(COILS):
        for suffix, label, color, style in runs:
            f, v = curves(f"d_{coil}_{suffix}" if "slot" in suffix else f"s_{coil}_{suffix}")
            keep = f <= f_max * 1e9
            axes[0, column].plot(f[keep] / 1e9, v["L_diff"][keep] * 1e9, color=color, ls=style, lw=2, label=label)
            axes[1, column].plot(f[keep] / 1e9, v["Q_diff"][keep], color=color, ls=style, lw=2, label=label)
        axes[0, column].set_title(coil_title, loc="left", fontsize=11, fontweight="bold")
        if limits:
            axes[0, column].set_ylim(*l_limits)
        axes[0, column].set_ylabel("Differential L (nH)")
        axes[1, column].set_ylabel("Differential Q")
        axes[1, column].set_ylim(bottom=0)
        axes[1, column].set_xlabel("Frequency (GHz)")
        axes[1, column].set_xlim(0, f_max)
    finish(fig, axes, axes[0, 0], title, out)


def shunt_figure(out):
    """Shunt path, both ports together: capacitance and conductance, floating against tie."""
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7), sharex=True, facecolor=SURFACE)
    for row, (coil, coil_title, _, _) in enumerate(COILS):
        for margin, color in MARGIN_COLOR.items():
            for variant, style, name in (("float", "-", "floating"), ("noPEC", "--", "tie")):
                f, v = curves(f"s_{coil}_g{margin}_{variant}")
                keep = f <= 10e9
                w = 2 * np.pi * f[keep]
                y = v["y_cm"][keep]
                label = f"{margin} µm, {name}"
                axes[row, 0].plot(f[keep] / 1e9, y.imag / w * 1e15, color=color, ls=style, lw=1.8, label=label)
                axes[row, 1].plot(f[keep] / 1e9, y.real * 1e3, color=color, ls=style, lw=1.8, label=label)
        axes[row, 0].set_title(coil_title, loc="left", fontsize=11, fontweight="bold")
        axes[row, 0].set_ylabel("Shunt capacitance (fF)")
        axes[row, 1].set_ylabel("Shunt conductance (mS)")
        axes[row, 0].set_ylim(bottom=0)
        axes[row, 1].set_ylim(bottom=0)
    for ax in axes[1]:
        ax.set_xscale("log")
        ax.set_xlim(0.1, 10)
        ax.set_xlabel("Frequency (GHz)")
    finish(fig, axes, axes[0, 0], "Frame margin and frame type, both ports together", out)


def layout_figure(out, coil="L0n5", D=87.1, margins=(30, 150), scale=2.6):
    """Tested layouts side by side at one scale (pixels per um), centered on the coil. The margin is dimensioned from
    the outer edge of the coil to the inner edge of the frame. The last panel also marks the ground strip to the ports."""
    import gdspy
    from gds_viewer import render_screenshot

    panels = []
    for margin in margins:
        cell = gdspy.GdsLibrary(infile=study.layout_file(coil, D, margin, False)).top_level()[0]
        (x0, y0), (x1, y1) = cell.get_bounding_box()
        buffer = io.BytesIO()
        render_screenshot(cell, buffer, width_px=round(scale * (x1 - x0)), fill_alpha=0.3)
        buffer.seek(0)
        panels.append((margin, (x0, x1, y0, y1), plt.imread(buffer)))

    pad = 24
    total_width = sum(image.shape[1] for _, _, image in panels) + pad * (len(panels) + 1)
    total_height = max(image.shape[0] for _, _, image in panels) + 2 * pad
    fig = plt.figure(figsize=(total_width / 100, total_height / 100), dpi=100, facecolor=SURFACE)
    color = "#ffd84d"
    left = pad
    for margin, extent, image in panels:
        height, width = image.shape[:2]
        ax = fig.add_axes((left / total_width, (total_height - height) / 2 / total_height,
                           width / total_width, height / total_height))
        ax.imshow(image, extent=extent, interpolation="nearest")
        ax.set_axis_off()
        ax.annotate("", xy=(D / 2 + margin, 0), xytext=(D / 2, 0),
                    arrowprops=dict(arrowstyle="<|-|>", color=color, lw=2.5, shrinkA=0, shrinkB=0, mutation_scale=18))
        ax.text(D / 2 + margin / 2, 2, f"margin\n{margin} µm", ha="center", va="bottom", color=color, fontsize=14)
        left += width + pad
    # at a small margin the strip is only a short stub at the ports, so it is marked in the last panel
    pointer = dict(arrowstyle="-|>", color=color, lw=2, shrinkA=4, shrinkB=0, mutation_scale=16)
    ax.annotate("Metal1 ground strip,\nfrom the frame to the ports", xy=(8.5, -135), xytext=(32, -135),
                ha="left", va="center", color=color, fontsize=14, arrowprops=pointer)
    ax.annotate("ports", xy=(-6, -73.55), xytext=(-40, -73.55), ha="right", va="center", color=color, fontsize=14,
                arrowprops=pointer)
    path = os.path.join(HERE, "plots", out)
    fig.savefig(path, dpi=100)
    plt.close(fig)
    print("wrote", path)


def plane_layout_figure(out, coil="L0n5", D=87.1, margin=30, scale=2.6):
    """The two layouts without a cutout, side by side."""
    import gdspy
    from gds_viewer import render_screenshot

    panels = []
    for tie, label in (("plane_M1", "solid Metal1 plane"), ("plane_M3", "solid Metal3 plane")):
        cell = gdspy.GdsLibrary(infile=study.layout_file(coil, D, margin, tie)).top_level()[0]
        (x0, y0), (x1, y1) = cell.get_bounding_box()
        buffer = io.BytesIO()
        render_screenshot(cell, buffer, width_px=round(scale * (x1 - x0)), fill_alpha=0.3)
        buffer.seek(0)
        panels.append((label, plt.imread(buffer)))
    pad, title = 24, 40
    height, width = panels[0][1].shape[:2]
    total_width, total_height = 2 * width + 3 * pad, height + 2 * pad + title
    fig = plt.figure(figsize=(total_width / 100, total_height / 100), dpi=100, facecolor=SURFACE)
    for k, (label, image) in enumerate(panels):
        left = pad + k * (width + pad)
        ax = fig.add_axes((left / total_width, pad / total_height, width / total_width, height / total_height))
        ax.imshow(image, interpolation="nearest")
        ax.set_axis_off()
        fig.text((left + width / 2) / total_width, (total_height - title / 2 - pad / 2) / total_height, label,
                 ha="center", va="center", fontsize=14, color=INK, fontweight="bold")
    path = os.path.join(HERE, "plots", out)
    fig.savefig(path, dpi=100, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path)


def plane_figure(out):
    """L and Q against frequency on a log axis, because L falls at around 1 GHz: frames against the solid planes."""
    runs = [("g150_float", "Frame, margin 150 µm", MARGIN_COLOR[150], "-"), ("g30_float", "Frame, margin 30 µm", MARGIN_COLOR[30], "-"),
            ("g30_planeM1", "No cutout, Metal1 plane", "#eb6834", "-"), ("g30_planeM3", "No cutout, Metal3 plane", "#a33e16", "--")]
    limits = {"L0n5": (40.0, (0.25, 0.60)), "L2n0": (15.0, (0.8, 2.6))}
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7), sharex="col", facecolor=SURFACE)
    for column, (coil, coil_title, _, _) in enumerate(COILS):
        f_max, l_limits = limits[coil]
        for suffix, label, color, style in runs:
            f, v = curves(f"s_{coil}_{suffix}")
            keep = f <= f_max * 1e9
            axes[0, column].plot(f[keep] / 1e9, v["L_diff"][keep] * 1e9, color=color, ls=style, lw=2, label=label)
            axes[1, column].plot(f[keep] / 1e9, v["Q_diff"][keep], color=color, ls=style, lw=2, label=label)
        axes[0, column].set_title(coil_title, loc="left", fontsize=11, fontweight="bold")
        axes[0, column].set_ylim(*l_limits)
        axes[0, column].set_ylabel("Differential L (nH)")
        axes[1, column].set_ylabel("Differential Q")
        axes[1, column].set_ylim(bottom=0)
        axes[1, column].set_xscale("log")
        axes[1, column].set_xlim(0.1, f_max)
        axes[1, column].set_xticks([0.1, 1, 10], ["0.1", "1", "10"])
        axes[1, column].set_xlabel("Frequency (GHz)")
    finish(fig, axes, axes[0, 0], "Frame or solid plane, same coil", out)


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
    layout_figure("layout_margin.png")
    plane_layout_figure("layout_plane.png")
    plane_figure("plane_L_Q.png")
    series_figure([(f"g{m}_float", f"{m} µm", c, "-") for m, c in MARGIN_COLOR.items()],
                  "Frame margin, floating Metal1 frame", "margin_L_Q.png")
    shunt_figure("margin_shunt.png")
    series_figure([("g150_float", "150 µm", MARGIN_COLOR[150], "-"), ("g10_float", "10 µm", MARGIN_COLOR[30], "-"),
                   ("g10_slot", "10 µm, ring cut", "#eb6834", "--")],
                  "Side note: floating Metal1 frame", "side_cut_ring.png", limits=False)
