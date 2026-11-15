#!/usr/bin/env python
"""L6n2 inductor (IHP SG13G2, 2 um mesh, conformal passivation, 'solve_inside'): distance to the absorbing boundary.

Two sweeps, each solved with Palace 0.19.0 and with Palace 0.18.1 (before its fix of the second-order absorbing
boundary):
  side margin 100/200/400/800 um, air around kept at 50 um
  air around 50/200/400/800 um at 400 um margin, plus 400 um air above and below only (50 um at the sides)

Reads results/snp/ and writes results/plots/story_boundary.png (peak Q for both sweeps) and prints the numbers
quoted in README.md. Measured values from ../../measured_vs_simulated/more_accurate_models_L6n2_v5.

Inductor figures of merit, ports 1/2 as one differential pair:
  Zdiff = Z11 - Z12 - Z21 + Z22,  L = Im(Zdiff)/w,  Q = Im(Zdiff)/Re(Zdiff)
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
MEAS = os.path.join(HERE, "..", "..", "..", "measured_vs_simulated", "more_accurate_models_L6n2_v5",
                    "meas_L5_6n2_THRU_deemb.S2P")

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3de"
BLUE, ORANGE = "#2a78d6", "#eb6834"
VERSIONS = (("0190", "Palace 0.19", BLUE, "o", "-"), ("0181", "Palace 0.18.1", ORANGE, "s", "--"))

MARGINS = [100, 200, 400, 800]   # air around 50 um
AIRS = [50, 200, 400, 800]       # margin 400 um


def fname(margin, air, version):
    return f"L6n2_margin{margin}_air{air}_palace{version}.s2p"


def merits(ntw):
    z = ntw.z
    zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    w = 2 * np.pi * ntw.f
    L = zd.imag / w * 1e9
    Q = zd.imag / zd.real
    srf = ntw.f[np.where(np.diff(np.sign(L)) < 0)[0]]
    return {"L1": np.interp(1e9, ntw.f, L), "Qpk": Q.max(), "fQ": ntw.f[Q.argmax()] / 1e9,
            "SRF": srf[0] / 1e9 if len(srf) else np.nan}


def load(margin, air, version):
    return merits(rf.Network(os.path.join(SNP_DIR, fname(margin, air, version))))


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)


def plot():
    meas = merits(rf.Network(MEAS)) if os.path.isfile(MEAS) else None
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0), sharey=True)
    for v, label, color, marker, ls in VERSIONS:
        axes[0].plot(MARGINS, [load(m, 50, v)["Qpk"] for m in MARGINS], color=color, marker=marker, markersize=8,
                     linewidth=2, linestyle=ls, label=label)
        axes[1].plot(AIRS, [load(400, a, v)["Qpk"] for a in AIRS], color=color, marker=marker, markersize=8,
                     linewidth=2, linestyle=ls, label=label)
        axes[1].plot([400], [load(400, "z400", v)["Qpk"]], color=color, marker=marker, markersize=9,
                     markerfacecolor="white", markeredgewidth=2, linestyle="none")
    axes[1].text(45, 14.72, "open markers: 400 µm air above and below,\n50 µm at the sides", fontsize=8, color=INK2)
    for ax in axes:
        style(ax)
        ax.set_xscale("log")
        ax.set_xticks([50, 100, 200, 400, 800])
        ax.set_xticklabels(["50", "100", "200", "400", "800"])
        if meas:
            ax.axhline(meas["Qpk"], color=INK2, linewidth=1, linestyle=":")
    if meas:
        axes[0].text(105, meas["Qpk"] + 0.03, "measured", fontsize=8, color=INK2)
    axes[0].set_xlim(80, 1000)
    axes[1].set_xlim(40, 1000)
    axes[0].set_title("Side margin, 50 µm air around", loc="left", fontsize=11, color=INK)
    axes[0].set_xlabel("settings['margin'] (µm)", color=INK2)
    axes[0].set_ylabel("Peak Q", color=INK2)
    axes[1].set_title("Air around, 400 µm margin", loc="left", fontsize=11, color=INK)
    axes[1].set_xlabel("settings['air_around'] (µm)", color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    out = os.path.join(PLOT_DIR, "story_boundary.png")
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def print_numbers():
    rows = [(m, 50) for m in MARGINS] + [(400, a) for a in AIRS[1:]] + [(400, "z400")]
    print(f"\n{'margin':>6s} {'air':>5s} | {'L@1GHz 0.18.1':>13s} {'0.19':>7s} | {'Qpk 0.18.1':>10s} {'0.19':>6s} {'gap':>6s} "
          f"| {'SRF':>5s}")
    for m, a in rows:
        r181, r19 = load(m, a, "0181"), load(m, a, "0190")
        print(f"{m:6d} {str(a):>5s} | {r181['L1']:13.4f} {r19['L1']:7.4f} | {r181['Qpk']:10.2f} {r19['Qpk']:6.2f} "
              f"{(r19['Qpk'] / r181['Qpk'] - 1) * 100:5.1f}% | {r19['SRF']:5.2f}")
    if os.path.isfile(MEAS):
        m = merits(rf.Network(MEAS))
        print(f"measured: L@1GHz {m['L1']:.4f} nH, peak Q {m['Qpk']:.2f} at {m['fQ']:.1f} GHz, SRF {m['SRF']:.2f} GHz")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    plot()
    print_numbers()
