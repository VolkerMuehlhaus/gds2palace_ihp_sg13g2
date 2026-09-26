#!/usr/bin/env python
"""Plots and numbers for README.md (ind_frame spiral inductor mesh study).

Reads the Touchstone files in results/snp/ and writes to results/plots/:

  story_uniform_LQ.png        - L and Q vs. frequency, uniform order-2 mesh 5 -> 1 um
  story_accuracy_vs_cost.png  - L and peak-Q error vs. solve time, order 1, order 2, AMR

It also prints the numbers quoted in README.md.

Inductor figures of merit, ports 1/2 taken as one differential pair:
  Zdiff = Z11 - Z12 - Z21 + Z22,  L = Im(Zdiff)/w,  Q = Im(Zdiff)/Re(Zdiff),  R = Re(Zdiff)
Reference for all errors: 1 um uniform mesh, order 2.
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

L_FREQ = 10e9  # frequency for the inductance comparison

# uniform order-2 sweep, coarse -> fine; ordinal blue ramp, light -> dark
UNIFORM = [
    ("5 µm", "ind_frame_mesh5.s2p", "#86b6ef"),
    ("3 µm", "ind_frame_mesh3.s2p", "#3987e5"),
    ("2 µm", "ind_frame_mesh2.s2p", "#1c5cab"),
    ("1 µm", "ind_frame_mesh1.s2p", "#0d366b"),
]
ORDER1 = [
    ("3 µm", "ind_frame_mesh3_order1.s2p"),
    ("2 µm", "ind_frame_mesh2_order1.s2p"),
    ("1 µm", "ind_frame_mesh1_order1.s2p"),
]
AMR = ("AMR final", "ind_frame_amr2_final.s2p")
REFERENCE = "ind_frame_mesh1.s2p"

# solve times in minutes, from the Palace logs of each run
SOLVE_MIN = {
    "ind_frame_mesh5.s2p": 47.5 / 60,
    "ind_frame_mesh3.s2p": 1 + 29 / 60,
    "ind_frame_mesh2.s2p": 2 + 20 / 60,
    "ind_frame_mesh1.s2p": 5 + 5 / 60,
    "ind_frame_mesh3_order1.s2p": 9.0 / 60,
    "ind_frame_mesh2_order1.s2p": 17.9 / 60,
    "ind_frame_mesh1_order1.s2p": 36.1 / 60,
    # AMR: cumulative over all iterations
    "ind_frame_amr2_final.s2p": 9 + 54 / 60,
}

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def lqr(ntw):
    z = ntw.z
    zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    w = 2 * np.pi * ntw.f
    return {"L": zd.imag / w * 1e9, "Q": zd.imag / zd.real, "R": zd.real}


def at(ntw, values, f_hz):
    return np.interp(f_hz, ntw.f, values)


def errors(fname, ref):
    """(L error at L_FREQ in %, peak-Q error in %) vs. the reference network."""
    ntw = load(fname)
    m, r = lqr(ntw), lqr(ref)
    dl = (at(ntw, m["L"], L_FREQ) / at(ref, r["L"], L_FREQ) - 1) * 100
    dq = (m["Q"].max() / r["Q"].max() - 1) * 100
    return dl, dq


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot_uniform_lq():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharex=True)
    for label, fname, color in UNIFORM:
        ntw = load(fname)
        m = lqr(ntw)
        for ax, key in zip(axes, ("L", "Q")):
            ax.plot(ntw.f / 1e9, m[key], color=color, linewidth=2, label=label)
    for ax, title in zip(axes, ("Differential inductance L (nH)", "Differential Q factor")):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    axes[0].set_ylim(0.6, 2.2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9,
               title="refined_cellsize (uniform, order 2)", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    out = os.path.join(PLOT_DIR, "story_uniform_LQ.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_accuracy_vs_cost():
    ref = load(REFERENCE)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    series = [
        ("order 2, uniform", [(l, f) for l, f, _ in UNIFORM[:-1]], BLUE, "o"),
        ("order 1, uniform", ORDER1, ORANGE, "s"),
    ]
    for name, runs, color, marker in series:
        xs = [SOLVE_MIN[f] for _, f in runs]
        errs = [errors(f, ref) for _, f in runs]
        for ax, idx in zip(axes, (0, 1)):
            ys = [abs(e[idx]) for e in errs]
            ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=8, label=name, zorder=3)
            for (label, _), x, y in zip(runs, xs, ys):
                ax.annotate(label, (x, y), textcoords="offset points", xytext=(6, 5), fontsize=8, color=INK)
    dl, dq = errors(AMR[1], ref)
    for ax, y in zip(axes, (abs(dl), abs(dq))):
        ax.plot([SOLVE_MIN[AMR[1]]], [y], color=AQUA, marker="D", markersize=9, linestyle="none",
                label="AMR, 2 iterations", zorder=3)
    for ax, title in zip(axes, (f"|L error| at {L_FREQ / 1e9:.0f} GHz (%)", "|Peak Q error| (%)")):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xscale("log")
        ax.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
        ax.set_xticklabels(["0.1", "0.2", "0.5", "1", "2", "5", "10"])
        ax.set_xlim(0.1, 15)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Solve time (min, log scale)", color=INK2)
        ax.axvline(SOLVE_MIN[REFERENCE], color=INK2, linewidth=1, linestyle=":")
    axes[1].text(SOLVE_MIN[REFERENCE], axes[1].get_ylim()[1], " 1 µm reference\n run (5 min)",
                 fontsize=8, color=INK2, va="top")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9,
               title="error vs. 1 µm uniform mesh, order 2", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    out = os.path.join(PLOT_DIR, "story_accuracy_vs_cost.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    ref = load(REFERENCE)
    rows = [(l + ", order 2", f) for l, f, _ in UNIFORM] + [(l + ", order 1", f) for l, f in ORDER1] + [AMR]
    print()
    print(f"{'variant':16s} {'L@1GHz':>7s} {'L@10GHz':>8s} {'dL%':>6s} {'Qpeak':>6s} {'@GHz':>5s} {'dQ%':>6s} "
          f"{'R@1GHz':>7s} {'R@10GHz':>8s} {'MaxdS':>7s} {'min':>5s}")
    for label, fname in rows:
        ntw = load(fname)
        m = lqr(ntw)
        dl, dq = errors(fname, ref)
        print(f"{label:16s} {at(ntw, m['L'], 1e9):7.4f} {at(ntw, m['L'], L_FREQ):8.4f} {dl:+6.2f} "
              f"{m['Q'].max():6.2f} {ntw.f[m['Q'].argmax()] / 1e9:5.1f} {dq:+6.2f} "
              f"{at(ntw, m['R'], 1e9):7.3f} {at(ntw, m['R'], L_FREQ):8.3f} "
              f"{np.abs(ntw.s - ref.s).max():7.4f} {SOLVE_MIN[fname]:5.1f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_uniform_lq()
    plot_accuracy_vs_cost()
    print_numbers()
