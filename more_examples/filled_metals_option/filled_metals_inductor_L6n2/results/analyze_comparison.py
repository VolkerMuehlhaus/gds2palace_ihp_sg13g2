#!/usr/bin/env python
"""Stackup (planar vs. conformal-3D-passivation) x conductor-model
(surface-impedance vs. filled_metals) x mesh (5/2/1 um) study for the L6n2
inductor, compared against measurement (meas_L5_6n2_THRU_deemb.S2P, already
de-embedded).

Reads de-embedded 2-port Touchstone files from results/snp/, computes
differential L/Q/Rseries (Zdiff = Z11-Z12-Z21+Z22, same convention as
filled_metals_inductor_L2n0/results/analyze_comparison.py and
mesh_convergence_inductor/results/plot_inductor_convergence.py), and renders
one 2-panel (L on top, Q on bottom) plot per stackup x conductor-model
combination, each overlaying its 3 mesh sizes plus the measured curve.

Also writes a cost table (DOF/mesh elements/solve time/peak RAM, from
palace_summary.py's own parsing) and an accuracy table (L/Q percent error vs.
measurement at 1/5/9 GHz - all below the measured SRF ~11.07 GHz).
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
STUDY_DIR = os.path.dirname(HERE)
PALACE_MODEL_DIR = os.path.join(STUDY_DIR, "palace_model")
PALACE_SUMMARY = r"D:\github-claude\gds2palace_ihp_sg13g2\scripts\palace_summary.py"

STACKUPS = [("planar", "Planar (flat SiO2+Passivation)"), ("conformal", "Conformal 3D-passivation")]
MODELS = [("surface", "Surface impedance"), ("volume", "filled_metals (volume)")]
MESHES = [(5, "5 um"), (2, "2 um"), (1, "1 um")]

COLORS = {5: "#55a868", 2: "#dd8452", 1: "#c44e52"}
STYLES = {5: ":", 2: "--", 1: "-"}
MEAS_COLOR = "#333333"

EVAL_FREQS_GHZ = [1.0, 5.0, 9.0]  # all below measured SRF ~11.07 GHz


def load(path):
    if not os.path.isfile(path):
        return None
    return rf.Network(path)


def diff_LQR(nw):
    z = nw.z
    z11, z12, z21, z22 = z[:, 0, 0], z[:, 0, 1], z[:, 1, 0], z[:, 1, 1]
    zdiff = z11 - z12 - z21 + z22
    freq = nw.frequency.f
    omega = freq * 2 * math.pi
    L = zdiff.imag / omega
    Q = zdiff.imag / zdiff.real
    R = zdiff.real
    return freq, L, Q, R


def value_at_freq(freq, values, freq_hz, tol_hz=0.3e9):
    idx = int(np.argmin(np.abs(freq - freq_hz)))
    if abs(freq[idx] - freq_hz) > tol_hz:
        return None
    return float(values[idx])


def find_srf_hz(freq, L):
    idx = np.where(np.diff(np.sign(L)))[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    f0, f1 = freq[i], freq[i + 1]
    l0, l1 = L[i], L[i + 1]
    return f0 - l0 * (f1 - f0) / (l1 - l0)


def parse_cost_table():
    """Run palace_summary.py over palace_model/ and parse its printed blocks
    into {combo_key: {dof, elements, time_s, ram_gb, err_norm, err_max}}."""
    result = subprocess.run(
        [sys.executable, PALACE_SUMMARY, PALACE_MODEL_DIR],
        capture_output=True, text=True)
    text = result.stdout
    blocks = re.split(r"----- (.*?) -----", text)[1:]  # alternating [path, block, path, block, ...]
    cost = {}
    for i in range(0, len(blocks), 2):
        path, block = blocks[i], blocks[i + 1]
        m = re.search(r"palace_L6n2_(\w+?)_(surface|volume)_(\d)um_data", path)
        if not m:
            continue
        key = f"{m.group(1)}_{m.group(2)}_{m.group(3)}um"
        dof = re.search(r"Degrees of freedom\s*:\s*([\d,]+)", block)
        elems = re.search(r"Mesh elements\s*:\s*([\d,]+)", block)
        time_m = re.search(r"Simulation time\s*:\s*(.+)", block)
        ram_m = re.search(r"Peak RAM\s*:\s*(.+)", block)
        cost[key] = {
            "dof": dof.group(1).strip() if dof else "n/a",
            "elements": elems.group(1).strip() if elems else "n/a",
            "time": time_m.group(1).strip() if time_m else "n/a",
            "ram": ram_m.group(1).strip() if ram_m else "n/a",
        }
    return cost


def main():
    os.makedirs(PLOT_DIR, exist_ok=True)

    measured = load(os.path.join(SNP_DIR, "measured.s2p"))
    if measured is None:
        print("WARNING: measured.s2p not found")
    meas_data = diff_LQR(measured) if measured is not None else None
    meas_srf = find_srf_hz(*meas_data[0:1], meas_data[1]) if meas_data else None
    if meas_srf:
        print(f"Measured SRF ~ {meas_srf/1e9:.2f} GHz")

    cost = parse_cost_table()

    # ---------------- per-combination L/Q plots ----------------
    all_series = {}  # key -> (freq, L, Q, R)
    for stackup_key, stackup_label in STACKUPS:
        for model_key, model_label in MODELS:
            combo_key = f"{stackup_key}_{model_key}"
            fig, (ax_l, ax_q) = plt.subplots(2, 1, figsize=(7.5, 8), sharex=True)

            if meas_data:
                mfreq, mL, mQ, _ = meas_data
                ax_l.plot(mfreq / 1e9, mL * 1e9, color=MEAS_COLOR, linestyle="-", linewidth=2.2, label="Measured")
                ax_q.plot(mfreq / 1e9, mQ, color=MEAS_COLOR, linestyle="-", linewidth=2.2, label="Measured")

            for mesh, mesh_label in MESHES:
                key = f"{stackup_key}_{model_key}_{mesh}um"
                nw = load(os.path.join(SNP_DIR, f"{key}.s2p"))
                if nw is None:
                    print(f"WARNING: missing {key}.s2p")
                    continue
                freq, L, Q, R = diff_LQR(nw)
                all_series[key] = (freq, L, Q, R)
                freq_ghz = freq / 1e9
                label = f"Sim, {mesh_label}"
                ax_l.plot(freq_ghz, L * 1e9, color=COLORS[mesh], linestyle=STYLES[mesh], label=label)
                ax_q.plot(freq_ghz, Q, color=COLORS[mesh], linestyle=STYLES[mesh], label=label)

            ax_l.set_ylabel("Diff. inductance L (nH)")
            ax_l.set_title(f"L6n2: {stackup_label} / {model_label}")
            ax_l.grid(True, alpha=0.3)
            ax_l.legend(fontsize=8)
            ax_l.set_xlim(0, 14)

            ax_q.set_ylabel("Diff. Q factor")
            ax_q.set_xlabel("Frequency (GHz)")
            ax_q.grid(True, alpha=0.3)
            ax_q.set_xlim(0, 14)
            ax_q.set_ylim(bottom=0)

            fig.tight_layout()
            out_path = os.path.join(PLOT_DIR, f"LQ_{combo_key}.png")
            fig.savefig(out_path, dpi=150)
            plt.close(fig)
            print(f"Wrote plot: {out_path}")

    # ---------------- cost table ----------------
    cost_csv = os.path.join(HERE, "cost_table.csv")
    with open(cost_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Stackup", "Conductor model", "Mesh", "DOF", "Mesh elements", "Solve time", "Peak RAM"])
        for stackup_key, stackup_label in STACKUPS:
            for model_key, model_label in MODELS:
                for mesh, mesh_label in MESHES:
                    key = f"{stackup_key}_{model_key}_{mesh}um"
                    c = cost.get(key, {})
                    writer.writerow([stackup_label, model_label, mesh_label,
                                      c.get("dof", "n/a"), c.get("elements", "n/a"),
                                      c.get("time", "n/a"), c.get("ram", "n/a")])
    print(f"Wrote cost table: {cost_csv}")

    # ---------------- accuracy vs. measurement table ----------------
    acc_csv = os.path.join(HERE, "accuracy_vs_measured_table.csv")
    with open(acc_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Stackup", "Conductor model", "Mesh", "Freq (GHz)",
                          "L (nH)", "L meas (nH)", "L err (%)",
                          "Q", "Q meas", "Q err (%)"])
        for stackup_key, stackup_label in STACKUPS:
            for model_key, model_label in MODELS:
                for mesh, mesh_label in MESHES:
                    key = f"{stackup_key}_{model_key}_{mesh}um"
                    if key not in all_series:
                        continue
                    freq, L, Q, R = all_series[key]
                    for g in EVAL_FREQS_GHZ:
                        L_val = value_at_freq(freq, L, g * 1e9)
                        Q_val = value_at_freq(freq, Q, g * 1e9)
                        L_meas = value_at_freq(meas_data[0], meas_data[1], g * 1e9) if meas_data else None
                        Q_meas = value_at_freq(meas_data[0], meas_data[2], g * 1e9) if meas_data else None
                        L_err = 100.0 * (L_val - L_meas) / L_meas if (L_val is not None and L_meas) else None
                        Q_err = 100.0 * (Q_val - Q_meas) / Q_meas if (Q_val is not None and Q_meas) else None
                        fmt = lambda x, nd=4: f"{x:.{nd}f}" if x is not None else "n/a"
                        writer.writerow([stackup_label, model_label, mesh_label, f"{g:.1f}",
                                          fmt(L_val * 1e9 if L_val is not None else None),
                                          fmt(L_meas * 1e9 if L_meas is not None else None),
                                          fmt(L_err, 2),
                                          fmt(Q_val), fmt(Q_meas), fmt(Q_err, 2)])
    print(f"Wrote accuracy table: {acc_csv}")


if __name__ == "__main__":
    main()
