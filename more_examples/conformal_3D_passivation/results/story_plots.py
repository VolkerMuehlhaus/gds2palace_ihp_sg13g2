#!/usr/bin/env python
"""Plots and numbers for README.md (D-band balun, conformal vs. planar passivation).

Reads the de-embedded Touchstone files of this study (results/snp/) and of the
planar-stackup mesh study (../../mesh_convergence/mesh_convergence_D-band_balun/
results/snp/) and writes to results/plots/:

  story_planar_vs_conformal.png - balun figures of merit vs. frequency, 1 um mesh,
                                  planar vs. conformal stackup, target band shaded
  story_mesh_vs_stackup.png     - S11 null frequency and Max|dS| vs. own 1 um result,
                                  over cell size, for both stackups

It also prints the numbers quoted in README.md.

Balun figures of merit (port 1 = input, ports 2/3 = balanced outputs):
  insertion loss   IL = -10*log10(|S21|^2 + |S31|^2)
  amplitude imb.   20*log10(|S21| / |S31|)
  phase imbalance  180 deg - |angle(S21 / S31)|
"""
import os
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLANAR_DIR = os.path.join(HERE, "..", "..", "mesh_convergence", "mesh_convergence_D-band_balun", "results", "snp")
PLOT_DIR = os.path.join(HERE, "plots")

BAND = (120e9, 160e9)

PLANAR = {m: os.path.join(PLANAR_DIR, f"balun_mesh{m}um.s3p") for m in (5, 4, 3, 2, 1)}
CONFORMAL = {m: os.path.join(SNP_DIR, f"balun_conformal_mesh{m}um.s3p") for m in (4, 2, 1)}

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"


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


def style(ax, band=True):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    if band:
        ax.axvspan(BAND[0] / 1e9, BAND[1] / 1e9, color="#f1efe8", zorder=0)


def plot_planar_vs_conformal():
    panels = [
        ("IL", "Insertion loss (dB)"),
        ("S11", "Input match |S11| (dB)"),
        ("amp", "Amplitude imbalance (dB)"),
        ("phase", "Phase imbalance (deg)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), sharex=True)
    for label, path, color in (("planar stackup", PLANAR[1], BLUE), ("conformal stackup", CONFORMAL[1], ORANGE)):
        ntw = rf.Network(path)
        m = merits(ntw)
        for ax, (key, _) in zip(axes.flat, panels):
            ax.plot(ntw.f / 1e9, m[key], color=color, linewidth=2, label=label)
    for ax, (_, title) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    axes[0, 0].text(140, 0.97, "target band", transform=axes[0, 0].get_xaxis_transform(),
                    ha="center", va="top", fontsize=8, color=INK2)
    for ax in axes[1]:
        ax.set_xlabel("Frequency (GHz)", color=INK2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=9,
               title="1 µm mesh, order 2", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(PLOT_DIR, "story_planar_vs_conformal.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def null_freq_ghz(path):
    ntw = rf.Network(path)
    return ntw.f[np.argmin(np.abs(ntw.s[:, 0, 0]))] / 1e9


def own_delta(runs, m):
    return np.abs(rf.Network(runs[m]).s - rf.Network(runs[1]).s).max()


def plot_mesh_vs_stackup():
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for label, runs, color, marker in (("planar", PLANAR, BLUE, "o"), ("conformal", CONFORMAL, ORANGE, "s")):
        cells = sorted(runs, reverse=True)
        axes[0].plot(cells, [null_freq_ghz(runs[m]) for m in cells], color=color, linewidth=2,
                     marker=marker, markersize=8, label=label)
        coarse = [m for m in cells if m != 1]
        axes[1].plot(coarse, [own_delta(runs, m) for m in coarse], color=color, linewidth=2,
                     marker=marker, markersize=8, label=label)
    shift = np.abs(rf.Network(PLANAR[1]).s - rf.Network(CONFORMAL[1]).s).max()
    axes[1].axhline(shift, color=INK2, linewidth=1.5, linestyle="--")
    axes[1].text(1.0, shift + 0.004, "planar vs. conformal stackup, both at 1 µm", fontsize=8, color=INK2,
                 ha="right", va="bottom")
    titles = ("S11 null frequency (GHz)", "Max |ΔS| vs. own 1 µm result")
    for ax, title in zip(axes, titles):
        style(ax, band=False)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("refined_cellsize (µm)", color=INK2)
        ax.set_xlim(5.3, 0.7)
        ax.set_xticks([5, 4, 3, 2, 1])
    axes[0].axhspan(BAND[0] / 1e9, BAND[1] / 1e9, color="#f1efe8", zorder=0)
    axes[0].text(1.0, BAND[1] / 1e9 - 0.5, "target band ", fontsize=8, color=INK2, ha="right", va="top")
    axes[1].set_ylim(0, 0.22)
    axes[0].legend(frameon=False, fontsize=9, loc="upper left", title="stackup", title_fontsize=9)
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "story_mesh_vs_stackup.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    print()
    print(f"In-band ({BAND[0] / 1e9:.0f}-{BAND[1] / 1e9:.0f} GHz), worst case over the band")
    print(f"{'run':14s} {'IL min..max':>13s} {'IL@120':>7s} {'IL@160':>7s} {'S11 max':>8s} {'S11@120':>8s} "
          f"{'S11@160':>8s} {'null GHz':>8s} {'|amp| max':>9s} {'phase':>11s} {'dS own1':>8s}")
    for name, runs in (("planar", PLANAR), ("conformal", CONFORMAL)):
        for mesh in sorted(runs, reverse=True):
            ntw = rf.Network(runs[mesh])
            m = merits(ntw)
            b = (ntw.f >= BAND[0]) & (ntw.f <= BAND[1])
            at = lambda k, f: np.interp(f, ntw.f, m[k])
            print(f"{name + f' {mesh} µm':14s} {m['IL'][b].min():5.2f}..{m['IL'][b].max():5.2f} "
                  f"{at('IL', 120e9):7.2f} {at('IL', 160e9):7.2f} {m['S11'][b].max():8.1f} "
                  f"{at('S11', 120e9):8.1f} {at('S11', 160e9):8.1f} {null_freq_ghz(runs[mesh]):8.0f} "
                  f"{np.abs(m['amp'][b]).max():9.2f} {m['phase'][b].min():5.1f}..{m['phase'][b].max():4.1f} "
                  f"{own_delta(runs, mesh):8.4f}")
    for mesh in (4, 2, 1):
        d = np.abs(rf.Network(PLANAR[mesh]).s - rf.Network(CONFORMAL[mesh]).s).max()
        print(f"planar vs. conformal at {mesh} µm: Max|dS| = {d:.4f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot_planar_vs_conformal()
    plot_mesh_vs_stackup()
    print_numbers()
