"""Differential and single-ended inductor values from Palace's port-S.csv."""
import csv
import glob
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
Z0 = 50.0


def read_y(name):
    """Frequencies in Hz, 2-port Y matrices."""
    path = glob.glob(os.path.join(HERE, "results", f"{name}_data", "output", "*", "port-S.csv"))[0]
    rows = [r for r in csv.reader(open(path)) if r]
    head = [h.strip() for h in rows[0]]
    data = np.array([[float(x) for x in r] for r in rows[1:]])

    def column(a, b, kind):
        return [i for i, h in enumerate(head) if f"S[{a}][{b}]" in h and kind in h][0]

    s = np.zeros((len(data), 2, 2), complex)
    for a in (1, 2):
        for b in (1, 2):
            s[:, a - 1, b - 1] = 10 ** (data[:, column(a, b, "dB")] / 20) * np.exp(1j * np.radians(data[:, column(a, b, "arg")]))
    identity = np.eye(2)
    y = np.array([np.linalg.inv(identity + m) @ (identity - m) / Z0 for m in s])
    return data[:, 0] * 1e9, y


def values(f, y):
    w = 2 * np.pi * f
    y_diff = (y[:, 0, 0] * y[:, 1, 1] - y[:, 0, 1] * y[:, 1, 0]) / (y[:, 0, 0] + y[:, 1, 1] + y[:, 0, 1] + y[:, 1, 0])
    z_diff = 1 / y_diff
    z_se = 1 / y[:, 0, 0]
    return {
        "L_diff": z_diff.imag / w, "Q_diff": z_diff.imag / z_diff.real, "R_diff": z_diff.real,
        "L_se": z_se.imag / w, "Q_se": z_se.imag / z_se.real,
        "y_cm": y[:, 0, 0] + y[:, 1, 1] + y[:, 0, 1] + y[:, 1, 0],
    }


def srf(f, x_im):
    """First zero crossing of the reactance, in Hz; None if inside the range."""
    for i in range(1, len(f)):
        if x_im[i - 1] > 0 >= x_im[i]:
            return f[i - 1] + (f[i] - f[i - 1]) * x_im[i - 1] / (x_im[i - 1] - x_im[i])
    return None


def at(f, value, frequency):
    return np.interp(frequency, f, value)


def summary(name):
    f, y = read_y(name)
    v = values(f, y)
    result = {"L_1G": at(f, v["L_diff"], 1e9) * 1e9}
    if len(f) > 5:
        result["Qpeak"] = float(v["Q_diff"].max())
        result["fQ"] = float(f[v["Q_diff"].argmax()] / 1e9)
        srf_diff = srf(f, v["L_diff"] * 2 * np.pi * f)
        result["SRF"] = srf_diff / 1e9 if srf_diff else None
        result["Qpeak_se"] = float(v["Q_se"].max())
        srf_se = srf(f, v["L_se"] * 2 * np.pi * f)
        result["SRF_se"] = srf_se / 1e9 if srf_se else None
    return result
