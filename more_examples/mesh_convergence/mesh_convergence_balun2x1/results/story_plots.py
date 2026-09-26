#!/usr/bin/env python
"""Plots and numbers for README.md (balun2x1 edge-coupled 2:1 balun mesh study).

Reads the de-embedded Touchstone files in results/snp/ and writes to results/plots/:

  story_uniform.png           - k, primary Q, |Sdd21|, |Sdd11| vs. frequency, uniform order-2 mesh
  story_accuracy_vs_cost.png  - peak-Q error and Max|dS| vs. solve time, order 1, order 2, AMR

It also prints the numbers quoted in README.md.

Figures of merit, ports 1/2 = primary pair, ports 3/4 = secondary pair:
  Zp = Z11 - Z12 - Z21 + Z22,  Zs = Z33 - Z34 - Z43 + Z44,  Zm = Z13 - Z14 - Z23 + Z24
  L = Im(Z)/w,  Q = Im(Z)/Re(Z),  k = |Im(Zm)| / sqrt(Im(Zp) * Im(Zs))
  Sdd11, Sdd21: differential 2-port (Zp, Zm, Zm, Zs) converted to S at the
  system impedances 200 ohm (primary) and 50 ohm (secondary).
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

Z01, Z02 = 200.0, 50.0
L_FREQ = 10e9
F_COIL_MAX = 25e9  # primary self-resonance at 27-30 GHz; L, k, Q lose their meaning above

UNIFORM = [
    ("5 µm", "balun2x1_mesh5.s4p", "#86b6ef"),
    ("2 µm", "balun2x1_mesh2.s4p", "#2a78d6"),
    ("1 µm", "balun2x1_mesh1.s4p", "#0d366b"),
]
ORDER1 = [
    ("5 µm", "balun2x1_mesh5_order1.s4p"),
    ("2 µm", "balun2x1_mesh2_order1.s4p"),
    ("1 µm", "balun2x1_mesh1_order1.s4p"),
]
AMR = ("AMR final", "balun2x1_amr2_final.s4p")
REFERENCE = "balun2x1_mesh1.s4p"

# solve times in minutes, from the Palace logs; AMR value is cumulative over all iterations
SOLVE_MIN = {
    "balun2x1_mesh5.s4p": 4 + 3 / 60,
    "balun2x1_mesh2.s4p": 11 + 18 / 60,
    "balun2x1_mesh1.s4p": 27 + 5 / 60,
    "balun2x1_mesh5_order1.s4p": 25.6 / 60,
    "balun2x1_mesh2_order1.s4p": 1 + 17 / 60,
    "balun2x1_mesh1_order1.s4p": 2 + 24 / 60,
    "balun2x1_amr2_final.s4p": 32 + 36 / 60,
}

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def merits(ntw):
    z = ntw.z
    w = 2 * np.pi * ntw.f
    zp = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    zs = z[:, 2, 2] - z[:, 2, 3] - z[:, 3, 2] + z[:, 3, 3]
    zm = z[:, 0, 2] - z[:, 0, 3] - z[:, 1, 2] + z[:, 1, 3]
    d = (zp + Z01) * (zs + Z02) - zm * zm
    sdd11 = ((zp - Z01) * (zs + Z02) - zm * zm) / d
    sdd21 = 2 * zm * np.sqrt(Z01 * Z02) / d
    return {
        "Lp": zp.imag / w * 1e9,
        "Ls": zs.imag / w * 1e9,
        "Qp": zp.imag / zp.real,
        "Qs": zs.imag / zs.real,
        "k": np.abs(zm.imag) / np.sqrt(np.abs(zp.imag * zs.imag)),
        "Sdd21": 20 * np.log10(np.abs(sdd21)),
        "Sdd11": 20 * np.log10(np.abs(sdd11)),
    }


def at(ntw, values, f_hz):
    return np.interp(f_hz, ntw.f, values)


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot_uniform():
    panels = [
        ("k", "Coupling factor k"),
        ("Qp", "Primary Q"),
        ("Sdd21", "|Sdd21| at 200 Ω / 50 Ω (dB)"),
        ("Sdd11", "|Sdd11| at 200 Ω / 50 Ω (dB)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6))
    for label, fname, color in UNIFORM:
        ntw = load(fname)
        m = merits(ntw)
        coil_range = ntw.f <= F_COIL_MAX
        for ax, (key, _) in zip(axes.flat, panels):
            sel = coil_range if key in ("k", "Qp") else slice(None)
            ax.plot(ntw.f[sel] / 1e9, m[key][sel], color=color, linewidth=2, label=label)
    for ax, (_, title) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    axes[1, 0].set_ylim(-3, -1)
    for ax in axes.flat:
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9,
               title="refined_cellsize (uniform, order 2)", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(PLOT_DIR, "story_uniform.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_accuracy_vs_cost():
    ref = load(REFERENCE)
    q_ref = merits(ref)["Qp"].max()

    def err(fname):
        ntw = load(fname)
        return (abs(merits(ntw)["Qp"].max() / q_ref - 1) * 100, np.abs(ntw.s - ref.s).max())

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    series = [
        ("order 2, uniform", [(l, f) for l, f, _ in UNIFORM[:-1]], BLUE, "o"),
        ("order 1, uniform", ORDER1, ORANGE, "s"),
    ]
    for name, runs, color, marker in series:
        xs = [SOLVE_MIN[f] for _, f in runs]
        errs = [err(f) for _, f in runs]
        for ax, idx in zip(axes, (0, 1)):
            ys = [e[idx] for e in errs]
            ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=8, label=name, zorder=3)
            for (label, _), x, y in zip(runs, xs, ys):
                ax.annotate(label, (x, y), textcoords="offset points", xytext=(6, 5), fontsize=8, color=INK)
    e_amr = err(AMR[1])
    for ax, y in zip(axes, e_amr):
        ax.plot([SOLVE_MIN[AMR[1]]], [y], color=AQUA, marker="D", markersize=9, linestyle="none",
                label="AMR, 2 iterations", zorder=3)
    for ax, title in zip(axes, ("|Peak primary Q error| (%)", "Max |ΔS| (linear)")):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xscale("log")
        ax.set_xticks([0.2, 0.5, 1, 2, 5, 10, 20, 50])
        ax.set_xticklabels(["0.2", "0.5", "1", "2", "5", "10", "20", "50"])
        ax.set_xlim(0.2, 60)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Solve time (min, log scale)", color=INK2)
        ax.axvline(SOLVE_MIN[REFERENCE], color=INK2, linewidth=1, linestyle=":")
    axes[0].text(SOLVE_MIN[REFERENCE], axes[0].get_ylim()[1], " 1 µm reference\n run (27 min)",
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
    print(f"{'variant':15s} {'Lp@10':>6s} {'Ls@10':>6s} {'k@10':>6s} {'Qp pk':>6s} {'Qs pk':>6s} "
          f"{'Sdd21 pk':>8s} {'@GHz':>5s} {'Sdd11 min':>9s} {'MaxdS':>7s} {'min':>5s}")
    for label, fname in rows:
        ntw = load(fname)
        m = merits(ntw)
        print(f"{label:15s} {at(ntw, m['Lp'], L_FREQ):6.3f} {at(ntw, m['Ls'], L_FREQ):6.3f} "
              f"{at(ntw, m['k'], L_FREQ):6.3f} {m['Qp'].max():6.2f} {m['Qs'].max():6.2f} "
              f"{m['Sdd21'].max():8.2f} {ntw.f[m['Sdd21'].argmax()] / 1e9:5.0f} {m['Sdd11'].min():9.1f} "
              f"{np.abs(ntw.s - ref.s).max():7.4f} {SOLVE_MIN[fname]:5.1f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_uniform()
    plot_accuracy_vs_cost()
    print_numbers()
