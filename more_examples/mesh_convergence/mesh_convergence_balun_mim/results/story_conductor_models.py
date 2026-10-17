#!/usr/bin/env python
"""Plot and numbers for README.md section "Conductor model": surface impedance (the mesh study above) vs. conductors meshed as
volumes: settings['conductor_model'] = 'solve_inside' and 'solve_inside_skin'.

Writes results/plots/story_conductor_models.png (insertion loss and input match vs. frequency) and prints the numbers
quoted in README.md. Reference: 'solve_inside_skin', 1 um mesh. DOF from the Palace output of each run.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import story_plots as S

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RUNS = [  # label, Touchstone file, DOF, color, line style
    ("surface impedance, 1 µm", "trans_100diff_to_80se_ports_mesh1.s3p", 1951380, BLUE, "-"),
    ("solve_inside, 2 µm", "trans_100diff_to_80se_ports_filled_mesh2.s3p", 1150620, ORANGE, "--"),
    ("solve_inside_skin, 2 µm", "trans_100diff_to_80se_ports_skin_mesh2.s3p", 1657992, AQUA, "--"),
    ("solve_inside_skin, 1 µm", "trans_100diff_to_80se_ports_skin_mesh1.s3p", 3629376, S.INK, "-"),
]
TABLE = RUNS[-1:] + [("solve_inside_skin, 2 µm", "trans_100diff_to_80se_ports_skin_mesh2.s3p", 1657992, None, None),
                     ("solve_inside_skin, 3 µm", "trans_100diff_to_80se_ports_skin_mesh3.s3p", 1143524, None, None),
                     ("solve_inside, 2 µm", "trans_100diff_to_80se_ports_filled_mesh2.s3p", 1150620, None, None),
                     ("surface impedance, 1 µm", "trans_100diff_to_80se_ports_mesh1.s3p", 1951380, None, None),
                     ("surface impedance, 2 µm", "trans_100diff_to_80se_ports_mesh2.s3p", 948860, None, None)]
REFERENCE = "trans_100diff_to_80se_ports_skin_mesh1.s3p"


def plot():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharex=True)
    for label, fname, _, color, ls in RUNS:
        ntw = S.load(fname)
        m = S.merits(ntw)
        axes[0].plot(ntw.f / 1e9, m["IL"], color=color, linestyle=ls, linewidth=2, label=label)
        axes[1].plot(ntw.f / 1e9, m["Sss11"], color=color, linestyle=ls, linewidth=2, label=label)
    for ax, title in zip(axes, ("Insertion loss (dB)", "Input match |Sss11| (dB)")):
        S.style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=S.INK)
        ax.set_xlabel("Frequency (GHz)", color=S.INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(S.PLOT_DIR, "story_conductor_models.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def numbers():
    ref = S.merits(S.load(REFERENCE))
    print(f"\n17-22 GHz, relative to {REFERENCE}")
    print(f"{'model':30s} {'DOF':>10s} {'IL min..max':>12s} {'dIL max':>8s} {'Sss11 max':>9s} {'null':>6s} {'Sdd22 max':>9s} {'|ph| max':>8s}")
    for label, fname, dof, _, _ in TABLE:
        ntw = S.load(fname)
        m = S.merits(ntw)
        dil = m["IL"] - ref["IL"]
        print(f"{label:30s} {dof:10,d} {m['IL'].min():5.2f}..{m['IL'].max():5.2f} {dil[np.abs(dil).argmax()]:+8.2f} "
              f"{m['Sss11'].max():9.1f} {ntw.f[m['Sss11'].argmin()] / 1e9:5.1f}G {m['Sdd22'].max():9.1f} "
              f"{np.abs(m['phase']).max():8.2f}")


if __name__ == "__main__":
    plot()
    numbers()
