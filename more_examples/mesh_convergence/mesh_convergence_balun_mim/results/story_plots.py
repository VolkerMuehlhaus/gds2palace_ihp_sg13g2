#!/usr/bin/env python
"""Plot and numbers for README.md (MIM-loaded balun trans_100diff_to_80se_ports).

Reads the raw Touchstone files in results/snp/ and writes to results/plots/:

  story_balun.png - insertion loss, |Sss11|, |Sdd22| and phase imbalance vs. frequency,
                    uniform mesh 3 -> 1 um plus AMR final

It also prints the numbers quoted in README.md.

Figures of merit at the true system impedances, port 1 = single-ended input (80 ohm),
ports 2/3 = differential output (100 ohm):
  the 3-port Z-matrix is reduced to a single-ended/differential 2-port
    Zaa = Z11, Zab = Z12 - Z13, Zba = Z21 - Z31, Zbb = Z22 - Z23 - Z32 + Z33
  and converted to S at Z01 = 80 ohm, Z02 = 100 ohm (see analyze_convergence.py).
  Insertion loss = -|Sds21| in dB.
  Balance: S21 and S31 renormalized to 80/50/50 ohm, amplitude imbalance
  |S21|/|S31| in dB, phase imbalance = angle(S21/S31) - 180 deg.
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

Z01, Z02 = 80.0, 100.0

# uniform sweep coarse -> fine (ordinal blue ramp), then AMR
RUNS = [
    ("3 µm", "trans_100diff_to_80se_ports.s3p", "#86b6ef", "-"),
    ("2 µm", "trans_100diff_to_80se_ports_mesh2.s3p", "#2a78d6", "-"),
    ("1 µm", "trans_100diff_to_80se_ports_mesh1.s3p", "#0d366b", "-"),
    ("AMR final", "trans_100diff_to_80se_ports_amr2.s3p", "#1baf7a", ":"),
]
REFERENCE = "trans_100diff_to_80se_ports_amr2.s3p"

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def merits(ntw):
    z = ntw.z
    zaa = z[:, 0, 0]
    zab = z[:, 0, 1] - z[:, 0, 2]
    zba = z[:, 1, 0] - z[:, 2, 0]
    zbb = z[:, 1, 1] - z[:, 1, 2] - z[:, 2, 1] + z[:, 2, 2]
    d = (zaa + Z01) * (zbb + Z02) - zab * zba
    sss11 = ((zaa - Z01) * (zbb + Z02) - zab * zba) / d
    sdd22 = ((zaa + Z01) * (zbb - Z02) - zab * zba) / d
    sds21 = 2 * zba * np.sqrt(Z01 * Z02) / d
    ren = ntw.copy()
    ren.renormalize([Z01, 50.0, 50.0])
    ratio = ren.s[:, 1, 0] / ren.s[:, 2, 0]
    phase = np.degrees(np.unwrap(np.angle(ratio)))
    phase -= 360 * np.round((phase.mean() - 180) / 360)
    return {
        "IL": -20 * np.log10(np.abs(sds21)),
        "Sss11": 20 * np.log10(np.abs(sss11)),
        "Sdd22": 20 * np.log10(np.abs(sdd22)),
        "amp": 20 * np.log10(np.abs(ratio)),
        "phase": phase - 180,
        "mm": np.stack([sss11, sds21, sdd22], axis=1),
    }


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot_balun():
    panels = [
        ("IL", "Insertion loss (dB)"),
        ("Sss11", "Input match |Sss11| at 80 Ω (dB)"),
        ("Sdd22", "Output match |Sdd22| at 100 Ω diff. (dB)"),
        ("phase", "Phase imbalance (deg)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), sharex=True)
    for label, fname, color, ls in RUNS:
        ntw = load(fname)
        m = merits(ntw)
        for ax, (key, _) in zip(axes.flat, panels):
            ax.plot(ntw.f / 1e9, m[key], color=color, linewidth=2, linestyle=ls, label=label)
    for ax, (_, title) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    axes[0, 0].set_ylim(1.0, 1.4)
    axes[1, 1].set_ylim(-2, 2)
    for ax in axes[1]:
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9,
               title="refined_cellsize (uniform, order 2) and AMR", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(PLOT_DIR, "story_balun.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    ref = merits(load(REFERENCE))
    print()
    print(f"{'run':10s} {'IL min..max':>13s} {'Sss11 max':>9s} {'null @GHz':>10s} {'Sdd22 max':>9s} "
          f"{'|amp| max':>9s} {'|ph| max':>8s} {'MaxdS vs AMR':>12s}")
    for label, fname, _, _ in RUNS:
        ntw = load(fname)
        m = merits(ntw)
        f = ntw.f / 1e9
        print(f"{label:10s} {m['IL'].min():5.2f}..{m['IL'].max():5.2f} {m['Sss11'].max():9.1f} "
              f"{f[m['Sss11'].argmin()]:10.1f} {m['Sdd22'].max():9.1f} {np.abs(m['amp']).max():9.2f} "
              f"{np.abs(m['phase']).max():8.2f} {np.abs(m['mm'] - ref['mm']).max():12.4f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_balun()
    print_numbers()
