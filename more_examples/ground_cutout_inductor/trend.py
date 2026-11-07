"""Values versus frame margin, printed as a table. Sweep results in results/s_<coil>_g<gap>_<float|tied>_data.

Shunt branch: the fit of the L6n2 study (Cox in series with Rsub parallel to Csub, 0.3 to 5 GHz, both ports together).
"""
import glob
import os
import re
import sys
from types import SimpleNamespace

import numpy as np

import analyze

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "..", "more_examples", "measured_vs_simulated", "more_accurate_models_L6n2_v3", "results")))
from shunt_parameters import fit_shunt  # noqa: E402


def row(name):
    f, y = analyze.read_y(name)
    v = analyze.values(f, y)
    w = 2 * np.pi * f
    cox, rsub, csub, rms = fit_shunt(SimpleNamespace(f=f, y=y))
    srf_diff = analyze.srf(f, v["L_diff"] * w)
    srf_se = analyze.srf(f, v["L_se"] * w)
    # peak Q below the SRF only: above it Q is negative, and the search stays clear of numerical noise at low frequency
    return dict(
        L1=analyze.at(f, v["L_diff"], 1e9) * 1e9, L5=analyze.at(f, v["L_diff"], 5e9) * 1e9,
        R1=analyze.at(f, v["R_diff"], 1e9), R5=analyze.at(f, v["R_diff"], 5e9),
        Q5=analyze.at(f, v["Q_diff"], 5e9),
        Qp=float(v["Q_diff"].max()), fQ=float(f[v["Q_diff"].argmax()]) / 1e9,
        SRF=srf_diff / 1e9 if srf_diff else float("nan"),
        Qse=float(v["Q_se"].max()), fQse=float(f[v["Q_se"].argmax()]) / 1e9,
        SRFse=srf_se / 1e9 if srf_se else float("nan"),
        Cox=cox * 1e15, Rsub=rsub, Csub=csub * 1e15, fit=rms * 100,
        C24=analyze.at(f, v["y_cm"].imag / w, 2.4e9) * 1e15, G24=analyze.at(f, v["y_cm"].real, 2.4e9) * 1e3,
    )


COLUMNS = ["L1", "L5", "R1", "R5", "Q5", "Qp", "fQ", "SRF", "Qse", "fQse", "SRFse", "Cox", "Rsub", "Csub", "fit", "C24", "G24"]


def table():
    names = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(HERE, "results", "s_*_data")))
    runs = []
    for name in names:
        match = re.match(r"s_(L\w+?)_g(\d+)_(float|tied|noPEC|planeM1|planeM3)", name)
        if glob.glob(os.path.join(HERE, "results", f"{name}_data", "output", "*", "port-S.csv")):
            runs.append((match[1], match[3], int(match[2]), name))
    print(f"{'run':24s}" + "".join(f"{c:>8s}" for c in COLUMNS))
    for coil, tie, gap, name in sorted(runs):
        values = row(name)
        print(f"{coil + ' ' + tie + ' ' + str(gap):24s}" + "".join(f"{values[c]:8.3f}" if values[c] < 100 else f"{values[c]:8.0f}" for c in COLUMNS))


if __name__ == "__main__":
    table()
