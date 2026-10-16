#!/usr/bin/env python
"""Plot and numbers for README.md section "Conductor model": surface impedance (the mesh study above) vs. filled metals
(settings['filled_metals'] = True or 'auto') with and without settings['skin_layers'] = True.

Writes results/plots/story_conductor_models.png (primary and secondary Q vs. frequency, 30 GHz marked) and prints the
numbers quoted in README.md. Reference: filled metals + skin layers, 1 um mesh. DOF from the Palace output of each run.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import story_plots as S

RUNS = [  # label, Touchstone file, DOF, color, line style
    ("surface impedance, 1 µm", "transformer_mesh1um.s5p", 576114, S.BLUE, "-"),
    ("filled 'auto', 2 µm", "transformer_auto_mesh2.s5p", 321664, S.BLUE, "--"),
    ("filled, 2 µm", "transformer_filled_mesh2.s5p", 371626, S.ORANGE, "--"),
    ("filled + skin layers, 2 µm", "transformer_skin_mesh2.s5p", 686496, S.AQUA, "--"),
    ("filled + skin layers, 1 µm", "transformer_skin_mesh1.s5p", 1461740, S.INK, "-"),
]
TABLE = RUNS[-1:] + [("filled + skin layers, 2 µm", "transformer_skin_mesh2.s5p", 686496, None, None),
                     ("filled + skin layers, 4 µm", "transformer_skin_mesh4.s5p", 352338, None, None),
                     ("filled + skin layers for 50 GHz, 2 µm", "transformer_skin50_mesh2.s5p", 674028, None, None),
                     ("filled, 2 µm", "transformer_filled_mesh2.s5p", 371626, None, None),
                     ("filled 'auto', 2 µm", "transformer_auto_mesh2.s5p", 321664, None, None),
                     ("surface impedance, 1 µm", "transformer_mesh1um.s5p", 576114, None, None),
                     ("surface impedance, 2 µm", "transformer_mesh2um.s5p", 312234, None, None)]
REFERENCE = "transformer_skin_mesh1.s5p"


def plot():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharex=True, sharey=True)
    for label, fname, _, color, ls in RUNS:
        ntw = S.load(fname)
        m = S.coil(ntw)
        keep = ntw.f <= S.F_PLOT_MAX
        for ax, key in zip(axes, ("Qp", "Qs")):
            ax.plot(ntw.f[keep] / 1e9, m[key][keep], color=color, linestyle=ls, linewidth=2, label=label)
    for ax, title in zip(axes, ("Primary Q", "Secondary Q")):
        S.style(ax)
        ax.axvline(S.F_DESIGN / 1e9, color=S.INK2, linewidth=1, linestyle=":")
        ax.set_title(title, loc="left", fontsize=11, color=S.INK)
        ax.set_xlabel("Frequency (GHz)", color=S.INK2)
    axes[0].set_xlim(0, S.F_PLOT_MAX / 1e9)
    axes[0].set_ylim(bottom=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    out = os.path.join(S.PLOT_DIR, "story_conductor_models.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def numbers():
    ref = S.load(REFERENCE)
    r = S.coil(ref)
    rv = {k: S.at(ref, r[k], S.F_DESIGN) for k in r}
    print(f"\nAt {S.F_DESIGN / 1e9:.0f} GHz, relative to {REFERENCE}")
    print(f"{'model':40s} {'DOF':>10s} {'Lp':>7s} {'dLp':>6s} {'k':>6s} {'dk':>6s} {'Qp':>6s} {'dQp':>7s} {'Qs':>6s} {'dQs':>7s}")
    for label, fname, dof, _, _ in TABLE:
        ntw = S.load(fname)
        m = S.coil(ntw)
        v = {k: S.at(ntw, m[k], S.F_DESIGN) for k in m}
        d = {k: 100 * (v[k] / rv[k] - 1) for k in v}
        print(f"{label:40s} {dof:10,d} {v['Lp']:7.4f} {d['Lp']:+5.1f}% {v['k']:6.4f} {d['k']:+5.1f}% "
              f"{v['Qp']:6.2f} {d['Qp']:+6.1f}% {v['Qs']:6.2f} {d['Qs']:+6.1f}%")


if __name__ == "__main__":
    plot()
    numbers()
