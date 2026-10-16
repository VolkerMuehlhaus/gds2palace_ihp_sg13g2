#!/usr/bin/env python
"""Plot and numbers for README.md section "Conductor model": surface impedance (the mesh study above) vs. filled metals
(settings['filled_metals'] = True or 'auto') with and without settings['skin_layers'] = True.

Writes results/plots/story_conductor_models.png (primary Q and |Sdd21| vs. frequency) and prints the numbers quoted
in README.md. Reference: filled metals + skin layers, 1 um mesh. DOF from the Palace output of each run.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import story_plots as S

RUNS = [  # label, Touchstone file, DOF, color, line style
    ("surface impedance, 1 µm", "balun2x1_mesh1.s4p", 1672974, S.BLUE, "-"),
    ("filled 'auto', 2 µm", "balun2x1_auto_mesh2.s4p", 905274, S.BLUE, "--"),
    ("filled, 2 µm", "balun2x1_filled_mesh2.s4p", 1016742, S.ORANGE, "--"),
    ("filled + skin layers, 2 µm", "balun2x1_skin_mesh2.s4p", 1678800, S.AQUA, "--"),
    ("filled + skin layers, 1 µm", "balun2x1_skin_mesh1.s4p", 3737648, S.INK, "-"),
]
TABLE = RUNS[-1:] + [("filled + skin layers, 2 µm", "balun2x1_skin_mesh2.s4p", 1678800, None, None),
                     ("filled + skin layers, 5 µm", "balun2x1_skin_mesh5.s4p", 598420, None, None),
                     ("filled, 2 µm", "balun2x1_filled_mesh2.s4p", 1016742, None, None),
                     ("filled 'auto', 2 µm", "balun2x1_auto_mesh2.s4p", 905274, None, None),
                     ("surface impedance, 1 µm", "balun2x1_mesh1.s4p", 1672974, None, None),
                     ("surface impedance, 2 µm", "balun2x1_mesh2.s4p", 843390, None, None)]
REFERENCE = "balun2x1_skin_mesh1.s4p"


def plot():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    for label, fname, _, color, ls in RUNS:
        ntw = S.load(fname)
        m = S.merits(ntw)
        coil = ntw.f <= S.F_COIL_MAX
        axes[0].plot(ntw.f[coil] / 1e9, m["Qp"][coil], color=color, linestyle=ls, linewidth=2, label=label)
        axes[1].plot(ntw.f / 1e9, m["Sdd21"], color=color, linestyle=ls, linewidth=2, label=label)
    for ax, title in zip(axes, ("Primary Q", "Differential transmission |Sdd21| (dB)")):
        S.style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=S.INK)
        ax.set_xlabel("Frequency (GHz)", color=S.INK2)
    axes[0].set_ylim(bottom=0)
    axes[1].set_xlim(15, 50)
    axes[1].set_ylim(-3.5, -1)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(S.PLOT_DIR, "story_conductor_models.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def numbers():
    ref = S.load(REFERENCE)
    r = S.merits(ref)
    c = ref.f <= S.F_COIL_MAX
    qp0, qs0 = r["Qp"][c].max(), r["Qs"][c].max()
    print(f"\nRelative to {REFERENCE}; L, k at {S.L_FREQ / 1e9:.0f} GHz, Q peaks below {S.F_COIL_MAX / 1e9:.0f} GHz")
    print(f"{'model':30s} {'DOF':>10s} {'Lp':>6s} {'k':>6s} {'Qp pk':>6s} {'dQp':>7s} {'Qs pk':>6s} {'dQs':>7s} {'Sdd21 pk':>8s} {'@GHz':>5s}")
    for label, fname, dof, _, _ in TABLE:
        ntw = S.load(fname)
        m = S.merits(ntw)
        c = ntw.f <= S.F_COIL_MAX
        qp, qs = m["Qp"][c].max(), m["Qs"][c].max()
        print(f"{label:30s} {dof:10,d} {S.at(ntw, m['Lp'], S.L_FREQ):6.3f} {S.at(ntw, m['k'], S.L_FREQ):6.3f} "
              f"{qp:6.2f} {100 * (qp / qp0 - 1):+6.1f}% {qs:6.2f} {100 * (qs / qs0 - 1):+6.1f}% "
              f"{m['Sdd21'].max():8.2f} {ntw.f[m['Sdd21'].argmax()] / 1e9:5.1f}")


if __name__ == "__main__":
    plot()
    numbers()
