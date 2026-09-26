#!/usr/bin/env python
"""Plots and numbers for README.md (D-band balun mesh study).

Reads the de-embedded Touchstone files in results/snp/ and writes two figures
to results/plots/ (new files only, the plots of analyze_convergence.py are not
touched):

  story_uniform_inband.png   - balun figures of merit vs. frequency, uniform
                               mesh 5 -> 1 um, target band 120-160 GHz shaded
  story_best_answers.png     - 2 um working point vs. 1 um, 2 um/order 3, AMR
  story_accuracy_vs_cost.png - Max|dS| vs. the 1 um result, over solve time,
                               for all variants

It also prints the in-band numbers quoted in README.md.

Balun figures of merit (port 1 = input, ports 2/3 = balanced outputs):
  insertion loss   IL = -10*log10(|S21|^2 + |S31|^2)   power not delivered to either output
  amplitude imb.   20*log10(|S21| / |S31|)
  phase imbalance  180 deg - |angle(S21 / S31)|         0 deg = ideal anti-phase
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

BAND = (120e9, 160e9)

# uniform sweep, coarse -> fine; ordinal blue ramp, light -> dark
UNIFORM = [
    ("5 µm", "balun_mesh5um.s3p", "#86b6ef"),
    ("4 µm", "balun_mesh4um.s3p", "#5598e7"),
    ("3 µm", "balun_mesh3um.s3p", "#2a78d6"),
    ("2 µm", "balun_mesh2um.s3p", "#1c5cab"),
    ("1 µm", "balun_mesh1um.s3p", "#0d366b"),
]
ORDER3 = ("2 µm, order 3", "balun_mesh2um_order3.s3p")
AMR = ("AMR final", "balun_amr5_final.s3p")
REFERENCE = "balun_mesh1um.s3p"

# solve times in minutes, from the Palace logs of each run
SOLVE_MIN = {
    "balun_mesh5um.s3p": 1 + 42 / 60,
    "balun_mesh4um.s3p": 1 + 55 / 60,
    "balun_mesh3um.s3p": 2 + 16 / 60,
    "balun_mesh2um.s3p": 3 + 14 / 60,
    "balun_mesh1um.s3p": 7 + 11 / 60,
    "balun_mesh2um_order3.s3p": 12 + 10 / 60,
    # AMR: Palace reports elapsed time cumulatively, so the final value covers all 5 iterations
    "balun_amr5_final.s3p": 142 + 31 / 60,
}

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
ORANGE = "#eb6834"
AQUA = "#1baf7a"


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def merits(ntw):
    s21 = ntw.s[:, 1, 0]
    s31 = ntw.s[:, 2, 0]
    s11 = ntw.s[:, 0, 0]
    return {
        "IL": -10 * np.log10(np.abs(s21) ** 2 + np.abs(s31) ** 2),
        "S11": 20 * np.log10(np.abs(s11)),
        "amp": 20 * np.log10(np.abs(s21) / np.abs(s31)),
        "phase": 180 - np.abs(np.angle(s21 / s31, deg=True)),
    }


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.axvspan(BAND[0] / 1e9, BAND[1] / 1e9, color="#f1efe8", zorder=0)


def plot_uniform_inband():
    panels = [
        ("IL", "Insertion loss (dB)"),
        ("S11", "Input match |S11| (dB)"),
        ("amp", "Amplitude imbalance (dB)"),
        ("phase", "Phase imbalance (deg)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), sharex=True)
    for label, fname, color in UNIFORM:
        ntw = load(fname)
        f = ntw.f / 1e9
        m = merits(ntw)
        for ax, (key, _) in zip(axes.flat, panels):
            ax.plot(f, m[key], color=color, linewidth=2, label=label)
    for ax, (_, title) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    for ax in axes[1]:
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    axes[0, 0].text(140, 0.97, "target band", transform=axes[0, 0].get_xaxis_transform(),
                    ha="center", va="top", fontsize=8, color=INK2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, fontsize=9,
               title="refined_cellsize (uniform, order 2)", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(PLOT_DIR, "story_uniform_inband.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_best_answers():
    """2 um working point vs. the three most expensive runs, IL and S11 only."""
    series = [
        ("2 µm (working point)", "balun_mesh2um.s3p", "#86b6ef", "-"),
        ("1 µm", "balun_mesh1um.s3p", "#0d366b", "-"),
        (ORDER3[0], ORDER3[1], ORANGE, "--"),
        (AMR[0], AMR[1], AQUA, ":"),
    ]
    panels = [("IL", "Insertion loss (dB)"), ("S11", "Input match |S11| (dB)")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharex=True)
    for label, fname, color, ls in series:
        ntw = load(fname)
        m = merits(ntw)
        for ax, (key, _) in zip(axes, panels):
            ax.plot(ntw.f / 1e9, m[key], color=color, linewidth=2, linestyle=ls, label=label)
    for ax, (_, title) in zip(axes, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    out = os.path.join(PLOT_DIR, "story_best_answers.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_accuracy_vs_cost():
    ref = load(REFERENCE)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    style(ax)
    ax.patches[-1].remove()  # no band shading on a time axis

    xs, ys = [], []
    for label, fname, color in UNIFORM[:-1]:
        d = np.abs(load(fname).s - ref.s).max()
        xs.append(SOLVE_MIN[fname])
        ys.append(d)
    ax.plot(xs, ys, color="#2a78d6", linewidth=2, marker="o", markersize=8, zorder=3,
            label="uniform mesh, order 2")
    for (label, _, _), x, y in zip(UNIFORM[:-1], xs, ys):
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(8, 4), fontsize=9, color=INK)

    for (label, fname), color, marker in ((ORDER3, ORANGE, "s"), (AMR, AQUA, "D")):
        d = np.abs(load(fname).s - ref.s).max()
        ax.plot([SOLVE_MIN[fname]], [d], color=color, marker=marker, markersize=9,
                linestyle="none", zorder=3, label=label)
        ax.annotate(label, (SOLVE_MIN[fname], d), textcoords="offset points",
                    xytext=(8, 4), fontsize=9, color=INK)

    ax.axvline(SOLVE_MIN[REFERENCE], color=INK2, linewidth=1, linestyle=":")
    ax.text(SOLVE_MIN[REFERENCE], 0.112, " 1 µm reference run (7 min)", fontsize=8, color=INK2,
            va="top")

    ax.set_xscale("log")
    ax.set_xlim(1, 400)
    ax.set_ylim(0, 0.115)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.set_xticklabels(["1", "2", "5", "10", "20", "50", "100", "200"])
    ax.set_xlabel("Solve time (min, log scale; AMR = all 5 iterations)", color=INK2)
    ax.set_ylabel("Max |ΔS| vs. 1 µm result", color=INK2)
    ax.legend(frameon=False, fontsize=9, loc="upper right", bbox_to_anchor=(1.0, 0.9))
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "story_accuracy_vs_cost.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    ref = load(REFERENCE)
    rows = [(l, f) for l, f, _ in UNIFORM] + [ORDER3, AMR]
    print()
    print("In-band (120-160 GHz) figures of merit; worst case over the band")
    print(f"{'variant':15s} {'IL min..max':>14s} {'S11 max':>8s} {'|amp| max':>9s} {'phase max':>9s} {'MaxdS vs 1um':>12s}")
    for label, fname in rows:
        ntw = load(fname)
        band = (ntw.f >= BAND[0]) & (ntw.f <= BAND[1])
        m = merits(ntw)
        d = np.abs(ntw.s - ref.s).max()
        print(f"{label:15s} {m['IL'][band].min():6.2f}..{m['IL'][band].max():5.2f} "
              f"{m['S11'][band].max():8.1f} {np.abs(m['amp'][band]).max():9.2f} "
              f"{m['phase'][band].max():9.1f} {d:12.4f}")
    # mutual agreement of the three most expensive answers
    print()
    print("Mutual Max|dS| of the three best answers:")
    best = {"1 µm": REFERENCE, ORDER3[0]: ORDER3[1], AMR[0]: AMR[1]}
    names = list(best)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = np.abs(load(best[names[i]]).s - load(best[names[j]]).s).max()
            print(f"  {names[i]} vs {names[j]}: {d:.4f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_uniform_inband()
    plot_best_answers()
    plot_accuracy_vs_cost()
    print_numbers()
