"""Collect the numbers of the L6n2 study's tables.

For every model: differential L at 1 GHz, peak Q below the SRF and SRF from results/<model>.s2p,
and unknowns (DOF), mesh elements, run time, peak memory, number of field solutions and linear solver
iterations from the Palace output in palace_model/<model>_data (palace.json), when that folder is there.
palace_model/ is not in the repository; without it only the values from the Touchstone files are printed.

Prints one table and writes results/run_data.csv (read by plot_speedup.py) when Palace output was found.

usage: python study_tables.py [study_dir] [run_data.csv]
defaults: the study folder this script sits in (results/..), and results/run_data.csv of that folder
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np
import skrf as rf

here = os.path.dirname(os.path.abspath(__file__))
study_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(here)
res = os.path.join(study_dir, "results")

# model name (without the L6n2_with_ports_ prefix) and its label in the README
MODELS = [
    ("surfacemesh_2um_viamerge", "Surface, 2 µm, via merge, no correction"),
    ("surfacemesh_2um_noviamerge", "Surface, 2 µm, no via merge"),
    ("surfacemesh_2um_mergecorrection", "Surface, 2 µm, via merge + correction"),
    ("2um_mergecorrection_filled", "Volume, 2 µm, planar"),
    ("2um_passicut", "Volume, 2 µm, PassiCut"),
    ("5um_passi3D", "Volume, 5 µm, conformal"),
    ("2um_passi3D", "Volume, 2 µm, conformal"),
    ("1um_passi3D", "Volume, 1 µm, conformal"),
    ("2um_passi3D_margin100", "Volume, 2 µm, conformal, margin 100 µm"),
    ("2um_passi3D_margin200", "Volume, 2 µm, conformal, margin 200 µm"),
    ("2um_passi3D_margin800", "Volume, 2 µm, conformal, margin 800 µm"),
    ("2um_passi3D_testframe_ground", "Volume, 2 µm, conformal, test frame ground"),
]
MEAS = os.path.join(study_dir, "meas_L5_6n2_THRU_deemb.S2P")


def differential(path):
    """L at 1 GHz (nH), peak Q below the SRF, SRF (GHz) of the differential impedance"""
    nw = rf.Network(path)
    f = nw.f
    z = nw.z
    zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    L = zd.imag / (2 * math.pi * f)
    q = zd.imag / zd.real
    L1 = float(np.interp(1e9, f, L)) * 1e9
    down = np.where((zd.imag[:-1] > 0) & (zd.imag[1:] <= 0) & (f[:-1] > 1e9))[0]
    if len(down):
        i = down[0]
        srf = f[i] - zd.imag[i] * (f[i + 1] - f[i]) / (zd.imag[i + 1] - zd.imag[i])
        qpeak = float(q[: i + 1].max())
    else:
        srf, qpeak = float("nan"), float(q.max())
    return L1, qpeak, srf / 1e9


def palace_run(model):
    """numbers of the Palace run from palace.json, or None"""
    hits = glob.glob(os.path.join(study_dir, "palace_model", f"L6n2_with_ports_{model}_data", "output", "*", "palace.json"))
    if not hits:
        return None
    j = json.load(open(hits[0]))
    t = j["ElapsedTime"]["Durations"]
    return {
        "dof": j["Problem"]["DegreesOfFreedom"],
        "elements": j["Problem"]["MeshElements"],
        "time_s": t["Total"],
        "estimator_s": t["Solve"] + t["Construction"] + t["Estimation"],
        "ram_gb": j["PeakMemoryMegabytes"]["Total"] / 1024,
        "solves": j["LinearSolver"]["TotalSolves"],
        "iterations": j["LinearSolver"]["TotalIts"],
        "palace": j["GitTag"],
    }


def mmss(seconds):
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


Lm, Qm, Sm = differential(MEAS)
print(f"measured: L = {Lm:.3f} nH at 1 GHz, peak Q = {Qm:.2f}, SRF = {Sm:.2f} GHz\n")
print(f"{'model':45s} {'L nH':>6s} {'Q':>6s} {'SRF':>6s} {'dL %':>6s} {'dQ %':>6s} {'dSRF %':>6s} "
      f"{'DOF':>10s} {'elements':>9s} {'time':>8s} {'estim. s':>8s} {'RAM GB':>7s} {'solves':>6s} {'its':>5s} {'its/solve':>9s}")
rows = []
for model, label in MODELS:
    path = os.path.join(res, f"L6n2_with_ports_{model}.s2p")
    if not os.path.exists(path):
        continue
    L, Q, S = differential(path)
    line = (f"{label:45s} {L:6.3f} {Q:6.2f} {S:6.2f} {100 * (L / Lm - 1):+6.1f} {100 * (Q / Qm - 1):+6.1f} "
            f"{100 * (S / Sm - 1):+6.1f}")
    run = palace_run(model)
    if run:
        line += (f" {run['dof']:10,d} {run['elements']:9,d} {mmss(run['time_s']):>8s} {run['estimator_s']:8.0f} "
                 f"{run['ram_gb']:7.2f} {run['solves']:6d} {run['iterations']:5d} {run['iterations'] / run['solves']:9.1f}")
        rows.append([model, label, run["dof"], run["elements"], f"{run['time_s']:.1f}", f"{run['estimator_s']:.1f}",
                     f"{run['ram_gb']:.2f}", run["solves"], run["iterations"], run["palace"]])
    print(line)

if rows:
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(res, "run_data.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "label", "dof", "elements", "time_s", "estimator_s", "ram_gb", "solves", "iterations", "palace"])
        w.writerows(rows)
    print("\nwrote", out)
    print(f"all {len(rows)} runs together: {mmss(sum(float(r[4]) for r in rows))}")
