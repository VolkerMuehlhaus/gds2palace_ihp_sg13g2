#!/usr/bin/env python
""""Passicut" workaround stackup (SG13G2_200um_passicut.xml) for the L6n2
inductor: instead of deriving explicit 3D conformal SiO2-sidewall geometry
(the conformal_volume combination in analyze_comparison.py, expensive: 2.86M
DOF / 42 GB / 1h6m at 1 um), the SiO2 dielectric block is simply shortened by
TopMetal2's own thickness (Thickness="=15.7303-3"), so SiO2 now ends 1.5 um
above the bottom of TopMetal2 with the 0.4 um Passivation on top - correct in
the "valleys" between traces, no conformal coating on the metal itself. A 1D
stackup change, no derived-layer booleans, no extra mesh-refinement geometry. filled_metals kept throughout
(surface impedance not tried here - see analyze_comparison.py's finding that
conductor model, not stackup, controls the Q/R match).

Compares against the two most relevant results from the main study
(results/snp/): conformal_volume_1um (previous best match, but the expensive
3D-conformal geometry) and planar_volume_1um (previous cheapest, but poor
SRF match) - both re-used from results/snp/, not re-simulated.

Reads de-embedded 2-port Touchstone files, computes differential L/Q/Rseries
(same convention as analyze_comparison.py: Zdiff = Z11-Z12-Z21+Z22), writes
one 3-panel (L/Q/R) comparison plot, a cost table entry, and an accuracy
table entry.
"""
import csv
import math
import os
import re
import subprocess
import sys

import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")
PALACE_SUMMARY = r"D:\github-claude\gds2palace_ihp_sg13g2\scripts\palace_summary.py"
PASSICUT_PALACE_MODEL_DIR = r"D:\github-claude\gds2palace_ihp_sg13g2\test_data\filled_metals_inductor_L6n2\palace_model"

SERIES = [
    ("measured", "Measured", None, "#333333", "-", 2.2),
    ("conformal_volume_1um", "Conformal + filled_metals, 1 um (best, §3)", None, "#c44e52", "-", 1.4),
    ("planar_volume_1um", "Planar + filled_metals, 1 um (cheapest baseline, §3)", None, "#4c72b0", ":", 1.4),
    ("passicut_volume_5um", "Passicut + filled_metals, 5 um (new)", None, "#55a868", "--", 1.8),
    ("passicut_volume_2um", "Passicut + filled_metals, 2 um (new)", None, "#dd8452", "-", 1.8),
]

PLOT_XLIM_GHZ = (0, 14)
R_YLIM_MAX_OHM = 12
L_EVAL_FREQS_GHZ = [0.1, 4.0, 8.0]  # stays clear of the SRF region (measured SRF ~11.07 GHz)
Q_EVAL_FREQS_GHZ = [1.0, 5.0, 9.0]


def load(fname):
    path = os.path.join(SNP_DIR, fname)
    return rf.Network(path) if os.path.isfile(path) else None


def diff_LQR(nw):
    z = nw.z
    z11, z12, z21, z22 = z[:, 0, 0], z[:, 0, 1], z[:, 1, 0], z[:, 1, 1]
    zdiff = z11 - z12 - z21 + z22
    freq = nw.frequency.f
    omega = freq * 2 * math.pi
    return freq, zdiff.imag / omega, zdiff.imag / zdiff.real, zdiff.real


def value_at_freq(freq, values, freq_hz, tol_hz=0.3e9):
    idx = int(np.argmin(np.abs(freq - freq_hz)))
    if abs(freq[idx] - freq_hz) > tol_hz:
        return None
    return float(values[idx])


def parse_cost(model_dir, pattern):
    result = subprocess.run([sys.executable, PALACE_SUMMARY, model_dir], capture_output=True, text=True)
    text = result.stdout
    blocks = re.split(r"----- (.*?) -----", text)[1:]
    cost = {}
    for i in range(0, len(blocks), 2):
        path, block = blocks[i], blocks[i + 1]
        m = re.search(pattern, path)
        if not m:
            continue
        dof = re.search(r"Degrees of freedom\s*:\s*([\d,]+)", block)
        elems = re.search(r"Mesh elements\s*:\s*([\d,]+)", block)
        time_m = re.search(r"Simulation time\s*:\s*(.+)", block)
        ram_m = re.search(r"Peak RAM\s*:\s*(.+)", block)
        cost[m.group(1)] = {
            "dof": dof.group(1).strip() if dof else "n/a",
            "elements": elems.group(1).strip() if elems else "n/a",
            "time": time_m.group(1).strip() if time_m else "n/a",
            "ram": ram_m.group(1).strip() if ram_m else "n/a",
        }
    return cost


def main():
    os.makedirs(PLOT_DIR, exist_ok=True)

    networks = {}
    fnames = {
        "measured": "measured.s2p",
        "conformal_volume_1um": "conformal_volume_1um.s2p",
        "planar_volume_1um": "planar_volume_1um.s2p",
        "passicut_volume_5um": "passicut_volume_5um.s2p",
        "passicut_volume_2um": "passicut_volume_2um.s2p",
    }
    for key, fname in fnames.items():
        nw = load(fname)
        if nw is None:
            print(f"WARNING: missing {fname}")
            continue
        networks[key] = diff_LQR(nw)

    # ---------------- comparison plot ----------------
    fig, (ax_l, ax_q, ax_r) = plt.subplots(3, 1, figsize=(7.5, 11), sharex=True)
    for key, label, _unused, color, style, lw in SERIES:
        if key not in networks:
            continue
        freq, L, Q, R = networks[key]
        freq_ghz = freq / 1e9
        ax_l.plot(freq_ghz, L * 1e9, color=color, linestyle=style, linewidth=lw, label=label)
        ax_q.plot(freq_ghz, Q, color=color, linestyle=style, linewidth=lw, label=label)
        ax_r.plot(freq_ghz, R, color=color, linestyle=style, linewidth=lw, label=label)

    ax_l.set_ylabel("Diff. inductance L (nH)")
    ax_l.set_title("L6n2: \"passicut\" workaround vs. previous best/cheapest")
    ax_l.grid(True, alpha=0.3)
    ax_l.legend(fontsize=7.5)
    ax_l.set_xlim(*PLOT_XLIM_GHZ)

    ax_q.set_ylabel("Diff. Q factor")
    ax_q.grid(True, alpha=0.3)
    ax_q.legend(fontsize=7.5)
    ax_q.set_xlim(*PLOT_XLIM_GHZ)
    ax_q.set_ylim(bottom=0)

    ax_r.set_ylabel("Diff. series resistance R (Ohm)")
    ax_r.set_xlabel("Frequency (GHz)")
    ax_r.grid(True, alpha=0.3)
    ax_r.legend(fontsize=7.5)
    ax_r.set_xlim(*PLOT_XLIM_GHZ)
    ax_r.set_ylim(0, R_YLIM_MAX_OHM)

    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "LQR_passicut_comparison.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")

    # ---------------- cost table ----------------
    passicut_cost = parse_cost(PASSICUT_PALACE_MODEL_DIR, r"palace_L6n2_passicut_volume_(\d)um_data")
    cost_csv = os.path.join(HERE, "passicut_cost_table.csv")
    with open(cost_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Variant", "Mesh", "DOF", "Mesh elements", "Solve time", "Peak RAM"])
        for mesh in ("5", "2"):
            c = passicut_cost.get(mesh, {})
            writer.writerow([f"passicut + filled_metals", f"{mesh} um",
                              c.get("dof", "n/a"), c.get("elements", "n/a"),
                              c.get("time", "n/a"), c.get("ram", "n/a")])
    print(f"Wrote cost table: {cost_csv}")

    # ---------------- accuracy vs. measurement table ----------------
    # L at L_EVAL_FREQS_GHZ (interpolated - the measured file is log-spaced),
    # Q at Q_EVAL_FREQS_GHZ, one row per quantity/frequency.
    acc_csv = os.path.join(HERE, "passicut_accuracy_table.csv")
    fmt = lambda x, nd=4: f"{x:.{nd}f}" if x is not None else "n/a"
    with open(acc_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Variant", "Quantity", "Freq (GHz)", "Sim", "Meas", "Err (%)"])
        mfreq, mL, mQ, _ = networks["measured"]
        for key, label, *_ in SERIES:
            if key == "measured" or key not in networks:
                continue
            freq, L, Q, R = networks[key]
            for g in L_EVAL_FREQS_GHZ:
                L_val = float(np.interp(g * 1e9, freq, L))
                L_meas = float(np.interp(g * 1e9, mfreq, mL))
                L_err = 100.0 * (L_val - L_meas) / L_meas
                writer.writerow([label, "L (nH)", f"{g:g}", fmt(L_val * 1e9), fmt(L_meas * 1e9), fmt(L_err, 2)])
            for g in Q_EVAL_FREQS_GHZ:
                Q_val = value_at_freq(freq, Q, g * 1e9)
                Q_meas = value_at_freq(mfreq, mQ, g * 1e9)
                Q_err = 100.0 * (Q_val - Q_meas) / Q_meas if (Q_val is not None and Q_meas) else None
                writer.writerow([label, "Q", f"{g:g}", fmt(Q_val), fmt(Q_meas), fmt(Q_err, 2)])
    print(f"Wrote accuracy table: {acc_csv}")


if __name__ == "__main__":
    main()
