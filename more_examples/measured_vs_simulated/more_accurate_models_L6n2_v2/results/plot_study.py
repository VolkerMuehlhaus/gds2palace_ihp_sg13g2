"""Regenerate the L6n2 study's differential L/Q/R plots.

Same calculation, axis limits, colors and line styles as plot_inductor
(D:/github/plot_inductor/plot_inductor.py), but with explicit legend labels
instead of truncated file names, and saving to PNG instead of plt.show().

usage: python plot_study.py [study_dir] [out_dir]
defaults: the study folder this script sits in (results/..), and results/plots
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import skrf as rf

here = os.path.dirname(os.path.abspath(__file__))
study_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(here)
out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "plots")
res = os.path.join(study_dir, "results")

MEAS = (os.path.join(study_dir, "meas_L5_6n2_THRU_deemb.S2P"), "Measured (de-embedded)")
CONF_2UM = (os.path.join(res, "L6n2_with_ports_2um_passi3D.s2p"), "Sim: conformal passivation, 2 µm mesh")
CONF_1UM = (os.path.join(res, "L6n2_with_ports_1um_passi3D.s2p"), "Sim: conformal passivation, 1 µm mesh")
CONF_5UM = (os.path.join(res, "L6n2_with_ports_5um_passi3D.s2p"), "Sim: conformal passivation, 5 µm mesh")
PASSICUT = (os.path.join(res, "L6n2_with_ports_2um_passicut.s2p"), "Sim: passivation cut (valleys only), 2 µm mesh")

SURF_MERGE = (os.path.join(res, "L6n2_with_ports_surfacemesh_2um_viamerge.s2p"),
              "Sim: surface model, via merge, no correction")
SURF_NOMERGE = (os.path.join(res, "L6n2_with_ports_surfacemesh_2um_noviamerge.s2p"),
                "Sim: surface model, no via merge (individual vias)")
SURF_CORR = (os.path.join(res, "L6n2_with_ports_surfacemesh_2um_mergecorrection.s2p"),
             "Sim: surface model, via merge + fill factor correction")
PLANAR_FILLED = (os.path.join(res, "L6n2_with_ports_2um_mergecorrection_filled.s2p"),
                 "Sim: volume model (filled metals), via merge + correction")

PLOTS = {
    "via_array_merging.png": [MEAS, SURF_MERGE, SURF_NOMERGE, SURF_CORR],
    "surface_vs_filled.png": [MEAS, SURF_CORR, PLANAR_FILLED],
    "passi3D_2um.png": [MEAS, CONF_2UM],
    "passicut.png": [MEAS, CONF_2UM, PASSICUT],
    "passi3D_5um.png": [MEAS, CONF_5UM, CONF_2UM],
    "passi3D_1um.png": [MEAS, CONF_2UM, CONF_1UM],
}

colors = ['b', 'r', 'm', 'c', 'g', 'y', 'k', 'w']
linestyles = ['solid', 'dashed', 'dashdot', 'dotted', 'solid', 'dashed', 'dashdot', 'dotted']


def get_diff_model(sub):
    z11 = sub.z[:, 0, 0]
    z21 = sub.z[:, 1, 0]
    z12 = sub.z[:, 0, 1]
    z22 = sub.z[:, 1, 1]
    Zdiff = z11 - z12 - z21 + z22
    freq = sub.frequency.f
    omega = freq * 2 * math.pi
    return freq, Zdiff.real, Zdiff.imag / omega, Zdiff.imag / Zdiff.real


def plot(entries, out_path):
    networks = []
    global_fmax = math.inf
    for path, label in entries:
        nw = rf.Network(path)
        networks.append((nw, label))
        global_fmax = min(global_fmax, max(nw.frequency.f))
    fspec = str(int(100e6 / 1e6)) + '-' + str(int(global_fmax / 1e6)) + 'mhz'

    Lmin, Rmin, Qmax = math.inf, math.inf, 0
    for nw, _ in networks:
        freq0, Rdiff0, Ldiff0, Qdiff0 = get_diff_model(nw[fspec])
        Lmin = min(Lmin, Ldiff0[1] * 1e9)
        Rmin = min(Rmin, Rdiff0[1])
        Qmax = max(Qmax, max(Qdiff0))
    # like plot_inductor: SRF-based x range from the LAST file's data
    srf_index = rf.util.find_nearest_index(Ldiff0, min(Ldiff0))
    plot_fmax_ghz = 1.2 * freq0[srf_index] / 1e9 if srf_index > 20 else global_fmax / 1e9
    Rs_index = rf.util.find_nearest_index(Rdiff0, rf.util.find_nearest(Rdiff0, 3 * Rmin))

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Differential Inductor Parameters")
    panels = [
        (axes[0, 0], lambda f, R, L, Q: L * 1e9, "Diff. Inductance (nH)", (0, 3 * Lmin), plot_fmax_ghz),
        (axes[0, 1], lambda f, R, L, Q: Q, "Diff. Q factor", (0, 1.2 * Qmax), plot_fmax_ghz),
        (axes[1, 0], lambda f, R, L, Q: R, "Diff. Resistance (Ohm)", (0, 5 * Rmin), plot_fmax_ghz),
        (axes[1, 1], lambda f, R, L, Q: R, "Diff. Resistance (Ohm)", (0.5 * Rmin, 3 * Rmin), freq0[Rs_index] / 1e9),
    ]
    for ax, value, ylabel, ylim, xmax in panels:
        ax.set_ylim(*ylim)
        ax.set_xlim(0, xmax)
        for n, (nw, label) in enumerate(networks):
            freq, R, L, Q = get_diff_model(nw[fspec])
            ax.plot(freq / 1e9, value(freq, R, L, Q), color=colors[n % 8], linestyle=linestyles[n % 8], label=label)
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel(ylabel)
        ax.set_xmargin(0)
        ax.legend(fontsize=9)
        ax.grid()
    fig.tight_layout()
    fig.savefig(out_path, dpi=125)
    plt.close(fig)
    print("wrote", out_path)


os.makedirs(out_dir, exist_ok=True)
for name, entries in PLOTS.items():
    plot(entries, os.path.join(out_dir, name))
