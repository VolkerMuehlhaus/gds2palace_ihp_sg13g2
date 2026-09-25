#!/usr/bin/env python
"""Plot and numbers for README.md (c4_frame_ports MOM capacitor, SG13CMOS5L).

Reads the raw Touchstone files in results/snp/ and writes to results/plots/:

  story_c12_vs_cost.png - C12 at 1 GHz vs. solve time, order 2 and order 3,
                          mesh 0.2 / 0.1 / 0.05 um

It also prints the numbers quoted in README.md.

C12 = -Im(Y12) / (2*pi*f), from the raw (not de-embedded) Y-parameters at 1 GHz.
"""
import os
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")

# (label, file, solve time in minutes from the Palace logs)
ORDER2 = [
    ("0.2 µm", "c4_frame_ports_mesh200nm.s2p", 0.5),
    ("0.1 µm", "c4_frame_ports_mesh100nm.s2p", 1 + 12 / 60),
    ("0.05 µm", "c4_frame_ports_mesh50nm.s2p", 3 + 23 / 60),
]
ORDER3 = [
    ("0.2 µm", "c4_frame_ports_mesh200nm_order3.s2p", 1 + 56 / 60),
    ("0.1 µm", "c4_frame_ports_mesh100nm_order3.s2p", 5 + 5 / 60),
    ("0.05 µm", "c4_frame_ports_mesh50nm_order3.s2p", 13 + 46 / 60),
]
SWEEP = "c4_frame_ports_mesh200nm_sweep.s2p"

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"


def c12_ff(fname):
    ntw = rf.Network(os.path.join(SNP_DIR, fname))
    return -ntw.y[:, 0, 1].imag / (2 * np.pi * ntw.f) * 1e15, ntw.f


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot_c12_vs_cost():
    fig, ax = plt.subplots(figsize=(8, 4.6))
    style(ax)
    for name, runs, color, marker in (("order 2", ORDER2, BLUE, "o"), ("order 3", ORDER3, ORANGE, "s")):
        xs = [t for _, _, t in runs]
        ys = [c12_ff(f)[0][0] for _, f, _ in runs]
        ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=8, label=name, zorder=3)
        for (label, _, _), x, y in zip(runs, xs, ys):
            ax.annotate(label, (x, y), textcoords="offset points", xytext=(7, 5), fontsize=8, color=INK)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 1, 2, 5, 10, 20])
    ax.set_xticklabels(["0.5", "1", "2", "5", "10", "20"])
    ax.set_xlim(0.4, 20)
    ax.set_xlabel("Solve time (min, log scale)", color=INK2)
    ax.set_ylabel("C12 at 1 GHz (fF)", color=INK2)
    ax.legend(frameon=False, fontsize=9, loc="upper right", title="FEM order, label = refined_cellsize",
              title_fontsize=8)
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "story_c12_vs_cost.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    best = c12_ff(ORDER3[-1][1])[0][0]
    print()
    print(f"{'run':18s} {'C12 fF':>7s} {'vs best':>8s} {'min':>6s}")
    for order, runs in (("order 2", ORDER2), ("order 3", ORDER3)):
        for label, fname, t in runs:
            c = c12_ff(fname)[0][0]
            print(f"{order + ', ' + label:18s} {c:7.3f} {(c / best - 1) * 100:+7.2f}% {t:6.1f}")
    c, f = c12_ff(SWEEP)
    print(f"sweep 0.2 µm/order 2: {c[0]:.2f} fF at {f[0] / 1e9:.2f} GHz, {c[-1]:.2f} fF at {f[-1] / 1e9:.0f} GHz "
          f"({(c[-1] / c[0] - 1) * 100:+.1f}%)")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_c12_vs_cost()
    print_numbers()
