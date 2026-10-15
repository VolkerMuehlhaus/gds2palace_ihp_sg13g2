#!/usr/bin/env python
"""Plot and numbers for README.md section "Conductor model": surface impedance (the mesh study above) vs. filled metals
(settings['filled_metals'] = True) with and without settings['skin_layers'] = True.

Writes results/plots/story_conductor_models.png (R and Q vs. frequency) and prints the numbers quoted in README.md.
Reference for all errors: filled metals + skin layers, 1 um mesh. DOF from the Palace output of each run.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import story_plots as S

RUNS = [  # label, Touchstone file, DOF, color, line style
    ("surface impedance, 1 µm", "ind_frame_mesh1.s2p", 881044, S.BLUE, "-"),
    ("filled, 2 µm", "ind_frame_filled_mesh2.s2p", 504076, S.ORANGE, "--"),
    ("filled + skin layers, 5 µm", "ind_frame_skin_mesh5.s2p", 382260, S.AQUA, ":"),
    ("filled + skin layers, 2 µm", "ind_frame_skin_mesh2.s2p", 1052830, S.AQUA, "--"),
    ("filled + skin layers, 1 µm", "ind_frame_skin_mesh1.s2p", 2375210, S.INK, "-"),
]
TABLE = RUNS + [("filled + skin layers, 3 µm", "ind_frame_skin_mesh3.s2p", 692654, None, None),
                ("surface impedance, 2 µm", "ind_frame_mesh2.s2p", 429096, None, None),
                ("surface impedance, 5 µm", "ind_frame_mesh5.s2p", 161484, None, None)]
REFERENCE = "ind_frame_skin_mesh1.s2p"


def plot():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharex=True)
    for label, fname, _, color, ls in RUNS:
        ntw = S.load(fname)
        m = S.lqr(ntw)
        for ax, key in zip(axes, ("R", "Q")):
            ax.plot(ntw.f / 1e9, m[key], color=color, linestyle=ls, linewidth=2, label=label)
    for ax, title in zip(axes, ("Differential resistance R (Ω)", "Differential Q factor")):
        S.style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=S.INK)
        ax.set_xlabel("Frequency (GHz)", color=S.INK2)
    axes[0].set_ylim(0, 12)
    axes[0].set_xlim(0, 40)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(S.PLOT_DIR, "story_conductor_models.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def numbers():
    ref = S.load(REFERENCE)
    r = S.lqr(ref)
    print(f"\n{'model':30s} {'DOF':>10s} {'R@1GHz':>7s} {'dR':>7s} {'L@10GHz':>8s} {'dL':>7s} {'Qpeak':>6s} {'@GHz':>5s} {'dQ':>7s}")
    for label, fname, dof, _, _ in TABLE:
        ntw = S.load(fname)
        m = S.lqr(ntw)
        r1, l10 = S.at(ntw, m["R"], 1e9), S.at(ntw, m["L"], 10e9)
        print(f"{label:30s} {dof:10,d} {r1:7.3f} {100 * (r1 / S.at(ref, r['R'], 1e9) - 1):+6.1f}% "
              f"{l10:8.4f} {100 * (l10 / S.at(ref, r['L'], 10e9) - 1):+6.2f}% "
              f"{m['Q'].max():6.2f} {ntw.f[m['Q'].argmax()] / 1e9:5.1f} {100 * (m['Q'].max() / r['Q'].max() - 1):+6.1f}%")


if __name__ == "__main__":
    plot()
    numbers()
