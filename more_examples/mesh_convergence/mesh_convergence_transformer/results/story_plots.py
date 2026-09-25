#!/usr/bin/env python
"""Plots and numbers for README.md (Transformer_IMN mesh study).

Reads the de-embedded Touchstone files in results/snp/ and writes to results/plots/:

  story_uniform_LkQ.png  - primary L, coupling k, primary and secondary Q vs. frequency,
                           uniform mesh 4 -> 1 um, 30 GHz design frequency marked
  story_convergence.png  - L, k and Q at 30 GHz vs. DOF, relative to the 1 um result,
                           uniform mesh and AMR final

It also prints the numbers quoted in README.md.

Coil figures of merit, from the 5-port Z-matrix (ports not used are open-circuited):
  primary   = differential port 1/2,  Zp = Z11 - Z12 - Z21 + Z22
  secondary = differential port 4/5,  Zs = Z44 - Z45 - Z54 + Z55
  mutual                              Zm = Z14 - Z15 - Z24 + Z25
  L = Im(Z)/w,  Q = Im(Z)/Re(Z),  k = |Im(Zm)| / sqrt(Im(Zp) * Im(Zs))
The center tap (port 3) is open in this reduction.
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

F_DESIGN = 30e9
F_PLOT_MAX = 40e9  # primary self-resonance near 47 GHz; k loses its meaning there

# uniform sweep, coarse -> fine; ordinal blue ramp, light -> dark (5 um crashed, see README)
UNIFORM = [
    ("4 µm", "transformer_mesh4um.s5p", "#86b6ef", 171460, "4m 2s"),
    ("3 µm", "transformer_mesh3um.s5p", "#3987e5", 209202, "4m 50s"),
    ("2 µm", "transformer_mesh2um.s5p", "#1c5cab", 312234, "7m 4s"),
    ("1 µm", "transformer_mesh1um.s5p", "#0d366b", 576114, "14m 4s"),
]
# Palace reports elapsed time cumulatively, so this covers all 3 AMR iterations
AMR = ("AMR final", "transformer_amr3_final.s5p", 2070680, "1h 47m")
REFERENCE = "transformer_mesh1um.s5p"

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
MAGENTA = "#e87ba4"


def load(fname):
    return rf.Network(os.path.join(SNP_DIR, fname))


def coil(ntw):
    z = ntw.z
    w = 2 * np.pi * ntw.f
    zp = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    zs = z[:, 3, 3] - z[:, 3, 4] - z[:, 4, 3] + z[:, 4, 4]
    zm = z[:, 0, 3] - z[:, 0, 4] - z[:, 1, 3] + z[:, 1, 4]
    return {
        "Lp": zp.imag / w * 1e9,
        "Ls": zs.imag / w * 1e9,
        "Qp": zp.imag / zp.real,
        "Qs": zs.imag / zs.real,
        "k": np.abs(zm.imag) / np.sqrt(np.abs(zp.imag * zs.imag)),
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
        ("Lp", "Primary inductance (nH)"),
        ("k", "Coupling factor k"),
        ("Qp", "Primary Q"),
        ("Qs", "Secondary Q"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), sharex=True)
    for label, fname, color, _, _ in UNIFORM:
        ntw = load(fname)
        sel = (ntw.f >= 1e9) & (ntw.f <= F_PLOT_MAX)
        m = coil(ntw)
        for ax, (key, _) in zip(axes.flat, panels):
            ax.plot(ntw.f[sel] / 1e9, m[key][sel], color=color, linewidth=2, label=label)
    for ax, (_, title) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.axvline(F_DESIGN / 1e9, color=INK2, linewidth=1, linestyle=":")
    axes[0, 0].text(F_DESIGN / 1e9, 0.97, " 30 GHz design", transform=axes[0, 0].get_xaxis_transform(),
                    fontsize=8, color=INK2, va="top")
    for ax in axes[1]:
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9,
               title="refined_cellsize (uniform, order 2)", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(PLOT_DIR, "story_uniform_LkQ.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_convergence():
    ref = load(REFERENCE)
    r = coil(ref)
    quantities = [("Lp", "primary L", BLUE, "o"), ("k", "coupling k", ORANGE, "s"),
                  ("Qp", "primary Q", AQUA, "D"), ("Qs", "secondary Q", MAGENTA, "^")]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    style(ax)
    ax.axhline(0, color=INK2, linewidth=1)
    for key, name, color, marker in quantities:
        ref_val = at(ref, r[key], F_DESIGN)
        xs, ys = [], []
        for _, fname, _, dof, _ in UNIFORM:
            ntw = load(fname)
            xs.append(dof)
            ys.append((at(ntw, coil(ntw)[key], F_DESIGN) / ref_val - 1) * 100)
        amr = load(AMR[1])
        y_amr = (at(amr, coil(amr)[key], F_DESIGN) / ref_val - 1) * 100
        ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=8, label=name, zorder=3)
        ax.plot([xs[-1], AMR[2]], [ys[-1], y_amr], color=color, linewidth=1.5, linestyle=":", zorder=2)
        ax.plot([AMR[2]], [y_amr], color=color, marker=marker, markersize=8, markerfacecolor="white",
                markeredgewidth=2, linestyle="none", zorder=3)
    for label, _, _, dof, _ in UNIFORM:
        ax.annotate(label, (dof, ax.get_ylim()[0]), textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=8, color=INK2)
    ax.annotate("AMR final\n(open markers)", (AMR[2], ax.get_ylim()[0]), textcoords="offset points",
                xytext=(0, 4), ha="center", fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.set_xlabel("Degrees of freedom (log scale)", color=INK2)
    ax.set_ylabel("Change vs. 1 µm result at 30 GHz (%)", color=INK2)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "story_convergence.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    ref = load(REFERENCE)
    print()
    print(f"Values at {F_DESIGN / 1e9:.0f} GHz")
    print(f"{'variant':10s} {'Lp nH':>7s} {'Ls nH':>7s} {'k':>7s} {'Qp':>6s} {'Qs':>6s} {'MaxdS vs 1um':>12s}")
    rows = [(l, f) for l, f, _, _, _ in UNIFORM] + [AMR[:2]]
    for label, fname in rows:
        ntw = load(fname)
        m = coil(ntw)
        v = {k: at(ntw, m[k], F_DESIGN) for k in m}
        d = np.abs(ntw.s - ref.s)[ntw.f >= 1e9].max()
        print(f"{label:10s} {v['Lp']:7.4f} {v['Ls']:7.4f} {v['k']:7.4f} {v['Qp']:6.2f} {v['Qs']:6.2f} {d:12.4f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_uniform()
    plot_convergence()
    print_numbers()
