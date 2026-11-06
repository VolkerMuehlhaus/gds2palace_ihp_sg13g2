"""Shunt path of the L6n2 inductor for two ground plates, compared to the measurement (README section 9).

The shunt branch is taken from the common-mode admittance (both ports tied together, Y11 + Y12 + Y21 + Y22) and
fitted from 0.3 to 5 GHz as an oxide capacitance Cox in series with the substrate, Rsub parallel to Csub.
Single-ended values are for port 2 grounded (1 / Y11), differential values as in plot_study.py.

Prints the table of section 9 and writes plots/shunt_ground.png.

usage: python shunt_parameters.py [file.s2p ...]
Without arguments: the measurement, the 2 um conformal model and the same model with the test frame ground.
With arguments: these Touchstone files instead, e.g. your own inductor results.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np
import skrf as rf
from scipy.optimize import least_squares

here = os.path.dirname(os.path.abspath(__file__))
study_dir = os.path.dirname(here)

DEFAULT = [
    (os.path.join(study_dir, "meas_L5_6n2_THRU_deemb.S2P"), "Measured (de-embedded)"),
    (os.path.join(here, "L6n2_with_ports_2um_passi3D.s2p"), "Sim: small ground plate (all other models)"),
    (os.path.join(here, "L6n2_with_ports_2um_passi3D_testframe_ground.s2p"), "Sim: ground plate of test frame size"),
]
FIT_RANGE = (0.3e9, 5e9)
Q_RANGE = (0.3e9, 12e9)     # search range for peak Q and SRF

colors = ['b', 'r', 'm', 'c', 'g', 'y', 'k']
linestyles = ['solid', 'dashed', 'dashdot', 'dotted', 'solid', 'dashed', 'dashdot']


def y_common(nw):
    """shunt admittance of both ports together"""
    y = nw.y
    return y[:, 0, 0] + y[:, 0, 1] + y[:, 1, 0] + y[:, 1, 1]


def fit_shunt(nw):
    """Cox (F), Rsub (Ohm), Csub (F) and the rms fit error (relative)"""
    sel = (nw.f >= FIT_RANGE[0]) & (nw.f <= FIT_RANGE[1])
    w = 2 * np.pi * nw.f[sel]
    y = y_common(nw)[sel]

    def residual(q):
        cox, rsub, csub = np.exp(q)
        model = 1 / (1 / (1j * w * cox) + 1 / (1 / rsub + 1j * w * csub))
        e = (model - y) / np.abs(y)
        return np.r_[e.real, e.imag]

    best = None
    for c0 in (60e-15, 120e-15, 250e-15):
        for r0 in (500.0, 2000.0):
            r = least_squares(residual, np.log([c0, r0, 30e-15]))
            if best is None or r.cost < best.cost:
                best = r
    cox, rsub, csub = np.exp(best.x)
    return cox, rsub, csub, np.sqrt(best.cost / len(w))


def peak_q_and_srf(f, z):
    """peak Q and the first zero crossing of the reactance within Q_RANGE"""
    sel = (f >= Q_RANGE[0]) & (f <= Q_RANGE[1])
    q = np.where(sel, z.imag / z.real, -np.inf)
    i = np.where(sel[:-1] & (z.imag[:-1] > 0) & (z.imag[1:] <= 0))[0]
    srf = np.nan
    if len(i):
        k = i[0]
        srf = f[k] + (f[k + 1] - f[k]) * z.imag[k] / (z.imag[k] - z.imag[k + 1])
    return q.max(), srf


def values(nw):
    cox, rsub, csub, rms = fit_shunt(nw)
    f = nw.f
    k = int(np.argmin(np.abs(f - 2.4e9)))
    z = nw.z
    q_se, srf_se = peak_q_and_srf(f, 1 / nw.y[:, 0, 0])
    q_diff, srf_diff = peak_q_and_srf(f, z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1])
    return [("Substrate resistance Rsub (Ohm)", "%.0f" % rsub),
            ("Substrate capacitance Csub (fF)", "%.0f" % (csub * 1e15)),
            ("Oxide capacitance Cox (fF)", "%.0f" % (cox * 1e15)),
            ("Fit error, rms (%)", "%.1f" % (rms * 100)),
            ("Shunt capacitance at 2.4 GHz, both ports (fF)", "%.0f" % (y_common(nw)[k].imag / (2 * np.pi * f[k]) * 1e15)),
            ("Single-ended SRF (GHz)", "%.2f" % (srf_se / 1e9)),
            ("Single-ended peak Q", "%.1f" % q_se),
            ("Differential peak Q", "%.2f" % q_diff),
            ("Differential SRF (GHz)", "%.2f" % (srf_diff / 1e9))]


def plot(networks, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Shunt path, both ports together")
    panels = [(axes[0], lambda f, y: y.imag / (2 * np.pi * f) * 1e15, "Shunt capacitance (fF)", (0, 180)),
              (axes[1], lambda f, y: y.real * 1e3, "Shunt conductance (mS)", (0, 1.2))]
    for ax, value, ylabel, ylim in panels:
        for n, (nw, label) in enumerate(networks):
            sel = (nw.f >= 0.1e9) & (nw.f <= 10e9)
            ax.plot(nw.f[sel] / 1e9, value(nw.f[sel], y_common(nw)[sel]), color=colors[n % 7],
                    linestyle=linestyles[n % 7], label=label)
        ax.set_xscale("log")
        ax.set_xlim(0.1, 10)
        ax.set_ylim(*ylim)
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
        ax.grid(which="both")
    fig.tight_layout()
    fig.savefig(out_path, dpi=125)
    plt.close(fig)
    print("wrote", out_path)


if __name__ == "__main__":
    entries = [(p, os.path.basename(p)) for p in sys.argv[1:]] or DEFAULT
    networks = [(rf.Network(path), label) for path, label in entries]
    columns = [values(nw) for nw, _ in networks]
    for n, (_, label) in enumerate(networks):
        print("column %d: %s" % (n + 1, label))
    for row in range(len(columns[0])):
        print("%-48s" % columns[0][row][0] + "".join("%10s" % c[row][1] for c in columns))
    if not sys.argv[1:]:
        os.makedirs(os.path.join(here, "plots"), exist_ok=True)
        plot(networks, os.path.join(here, "plots", "shunt_ground.png"))
