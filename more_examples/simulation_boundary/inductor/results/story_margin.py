#!/usr/bin/env python
"""Spiral inductor (ind_frame, 1 um mesh): 20, 50 and 100 um margin to the absorbing boundary, each solved with
Palace 0.19.0 and with Palace 0.18.1 (before its fix of the second-order absorbing boundary).

Reads results/snp/ and writes results/plots/story_margin.png:
  left:  Q vs. frequency, one color per margin, solid = Palace 0.19, dashed = Palace 0.18.1
  right: peak Q vs. margin for both Palace versions
and prints the numbers quoted in README.md.

Inductor figures of merit, ports 1/2 as one differential pair:
  Zdiff = Z11 - Z12 - Z21 + Z22,  L = Im(Zdiff)/w,  Q = Im(Zdiff)/Re(Zdiff),  R = Re(Zdiff)
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
L_FREQ = 10e9

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3de"
BLUE, ORANGE = "#2a78d6", "#eb6834"

# margin in um, Palace 0.19 file, Palace 0.18.1 file, color (ordinal ramp, light = close boundary)
RUNS = [
    (20, "ind_frame_margin20.s2p", "ind_frame_margin20_palace0181.s2p", "#86b6ef"),
    (50, "ind_frame_margin50.s2p", "ind_frame_margin50_palace0181.s2p", "#2a78d6"),
    (100, "ind_frame_margin100.s2p", "ind_frame_margin100_palace0181.s2p", "#0d366b"),
]


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def lqr(ntw):
    z = ntw.z
    zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    w = 2 * np.pi * ntw.f
    return {"L": zd.imag / w * 1e9, "Q": zd.imag / zd.real, "R": zd.real}


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot_margin():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    peaks = {"0.19": [], "0.18.1": []}
    for margin, f19, f181, color in RUNS:
        for fname, version, ls in ((f19, "0.19", "-"), (f181, "0.18.1", "--")):
            ntw = load(fname)
            q = lqr(ntw)["Q"]
            axes[0].plot(ntw.f / 1e9, q, color=color, linewidth=2, linestyle=ls,
                         label=f"{margin} µm, Palace {version}")
            peaks[version].append(q.max())
    margins = [r[0] for r in RUNS]
    axes[1].plot(margins, peaks["0.19"], color=BLUE, marker="o", markersize=8, linewidth=2, label="Palace 0.19")
    axes[1].plot(margins, peaks["0.18.1"], color=ORANGE, marker="s", markersize=8, linewidth=2, linestyle="--",
                 label="Palace 0.18.1")
    for ax in axes:
        style(ax)
    axes[0].set_title("Differential Q factor", loc="left", fontsize=11, color=INK)
    axes[0].set_xlabel("Frequency (GHz)", color=INK2)
    axes[0].set_xlim(10, 45)
    axes[0].set_ylim(15, 24)
    axes[1].set_title("Peak Q vs. margin", loc="left", fontsize=11, color=INK)
    axes[1].set_xlabel("Margin = air around (µm)", color=INK2)
    axes[1].set_xticks(margins)
    axes[1].legend(frameon=False, fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(PLOT_DIR, "story_margin.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    ref_ntw = load(RUNS[-1][1])
    ref = lqr(ref_ntw)
    ref_q, ref_l = ref["Q"].max(), np.interp(L_FREQ, ref_ntw.f, ref["L"])
    print(f"\n{'margin':>6s} {'Palace':>7s} {'L@10GHz':>8s} {'dL':>6s} {'R@10GHz':>8s} {'Qpeak':>6s} {'@GHz':>5s} {'dQ':>6s}"
          "   (d = vs. 100 um, Palace 0.19)")
    for margin, f19, f181, _ in RUNS:
        for fname, version in ((f19, "0.19"), (f181, "0.18.1")):
            ntw = load(fname)
            m = lqr(ntw)
            l10 = np.interp(L_FREQ, ntw.f, m["L"])
            print(f"{margin:6d} {version:>7s} {l10:8.4f} {(l10 / ref_l - 1) * 100:+5.2f}% "
                  f"{np.interp(L_FREQ, ntw.f, m['R']):8.3f} {m['Q'].max():6.2f} {ntw.f[m['Q'].argmax()] / 1e9:5.1f} "
                  f"{(m['Q'].max() / ref_q - 1) * 100:+5.1f}%")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_margin()
    print_numbers()
