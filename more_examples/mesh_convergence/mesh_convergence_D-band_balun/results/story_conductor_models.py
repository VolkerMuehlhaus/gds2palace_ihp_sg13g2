#!/usr/bin/env python
"""Plot and numbers for README.md section "Conductor model": surface impedance (the mesh study above) vs. filled metals
(settings['filled_metals'] = True or 'auto') with and without settings['skin_layers'] = True.

Writes results/plots/story_conductor_models.png (insertion loss and |S11| vs. frequency, target band shaded) and prints
the numbers quoted in README.md. Reference: filled metals + skin layers, 1 um mesh. DOF and GMRES iterations per
solve from the Palace output of each run.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import story_plots as S

BLUE = "#2a78d6"
RUNS = [  # label, Touchstone file, DOF, iterations per solve, color, line style
    ("surface impedance, 1 µm", "balun_mesh1um.s3p", 665874, None, BLUE, "-"),
    ("filled, 2 µm", "balun_filled_mesh2.s3p", 408116, 32, S.ORANGE, "--"),
    ("filled 'auto', 2 µm", "balun_auto_mesh2.s3p", 360744, 32, BLUE, "--"),
    ("filled + skin layers, 2 µm", "balun_skin_mesh2.s3p", 799550, 55, S.AQUA, "--"),
    ("filled + skin layers, 1 µm", "balun_skin_mesh1.s3p", 1736666, 44, S.INK, "-"),
]
TABLE = RUNS + [("filled + skin layers, 3 µm", "balun_skin_mesh3.s3p", 539578, 63, None, None),
                ("filled + skin layers, 5 µm", "balun_skin_mesh5.s3p", 389870, 82, None, None),
                ("surface impedance, 2 µm", "balun_mesh2um.s3p", 340226, None, None, None)]


def plot():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharex=True)
    for label, fname, _, _, color, ls in RUNS:
        ntw = S.load(fname)
        m = S.merits(ntw)
        axes[0].plot(ntw.f / 1e9, m["IL"], color=color, linestyle=ls, linewidth=2, label=label)
        axes[1].plot(ntw.f / 1e9, m["S11"], color=color, linestyle=ls, linewidth=2, label=label)
    for ax, title in zip(axes, ("Insertion loss (dB)", "Input match |S11| (dB)")):
        S.style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=S.INK)
        ax.set_xlabel("Frequency (GHz)", color=S.INK2)
    axes[0].set_ylim(0.8, 1.8)
    axes[0].text(155, 0.97, "target band", transform=axes[0].get_xaxis_transform(), ha="center", fontsize=8, color=S.INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(S.PLOT_DIR, "story_conductor_models.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def numbers():
    print(f"\nIn band {S.BAND[0] / 1e9:.0f}-{S.BAND[1] / 1e9:.0f} GHz")
    print(f"{'model':30s} {'DOF':>10s} {'it.':>4s} {'IL min..max':>12s} {'S11 max':>8s} {'S11 null':>9s} {'|amp| max':>9s} {'phase':>11s}")
    for label, fname, dof, it, _, _ in TABLE:
        ntw = S.load(fname)
        m = S.merits(ntw)
        b = (ntw.f >= S.BAND[0]) & (ntw.f <= S.BAND[1])
        print(f"{label:30s} {dof:10,d} {it if it else '-':>4} {m['IL'][b].min():5.2f}..{m['IL'][b].max():5.2f} "
              f"{m['S11'][b].max():8.1f} {ntw.f[np.argmin(m['S11'])] / 1e9:7.0f} G {np.abs(m['amp'][b]).max():9.2f} "
              f"{m['phase'][b].min():5.1f}..{m['phase'][b].max():4.1f}")


if __name__ == "__main__":
    plot()
    numbers()
