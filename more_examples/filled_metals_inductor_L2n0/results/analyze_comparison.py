#!/usr/bin/env python
"""Surface-impedance vs. filled_metals (bulk-conductivity volume) conductor
modeling comparison for the L_2n0_twoport differential inductor (IHP
SG13G2), at matched (surface_2/volume_2, 2um) and finer (volume_1, 1um)
mesh.

Reads RAW (not de-embedded) 2-port Touchstone files from results/snp/,
following the repo's mesh-convergence-study convention
(more_examples/mesh_convergence/AGENTS.md, SS2.6/2.7):
  - S-parameter overlay + delta-S tables (Max|dS|, standard HFSS-style
    convergence metric)
  - Differential L/Q/Rseries: Zdiff = Z11-Z12-Z21+Z22 (plain engineering
    convention, same as mesh_convergence_inductor/results/plot_inductor_convergence.py
    and the external plot_inductor.py utility it reimplements), then
    Ldiff = Im(Zdiff)/omega, Qdiff = Im(Zdiff)/Re(Zdiff), Rdiff = Re(Zdiff)

Eval frequency: 7 GHz (per user request), plus 1 GHz and 25 GHz for context
across the swept band.
"""
import os
import csv
import math
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")

SERIES = [
    ("surface_2um", "Surface, 2 um (baseline)", "surface_2um.s2p"),
    ("volume_2um", "filled_metals, 2 um", "volume_2um.s2p"),
    ("volume_1um", "filled_metals, 1 um", "volume_1um.s2p"),
]

COMPARISONS = [
    ("surface_2um", "volume_2um", "conductor modeling only (matched 2um mesh)"),
    ("volume_2um", "volume_1um", "mesh refinement only (filled_metals)"),
    ("surface_2um", "volume_1um", "combined (baseline vs. filled_metals as used)"),
]

EVAL_FREQS_GHZ = [1.0, 7.0, 20.0]  # 7 GHz is the requested design/eval frequency; SRF ~23 GHz
                                    # (see find_srf_hz below) so 20 GHz stays below resonance
FMIN_HZ = 100e6  # avoid divide-by-zero near DC

PARAMS = ["S11", "S21"]  # plain 2-port, S12=S21 by reciprocity


def load(entry):
    key, label, fname = entry
    path = os.path.join(SNP_DIR, fname)
    if not os.path.isfile(path):
        return None
    nw = rf.Network(path)
    nw.name = label
    fmax = nw.frequency.f.max()
    fspec = f"{int(FMIN_HZ/1e6)}-{int(fmax/1e6)}mhz"
    return key, label, nw[fspec]


def db(x):
    return 20 * np.log10(np.abs(x))


def deg(x):
    return np.angle(x, deg=True)


def s_traces(nw):
    s = nw.s
    return {"S11": s[:, 0, 0], "S21": s[:, 1, 0]}


def get_diff_model(nw):
    z = nw.z
    z11, z12, z21, z22 = z[:, 0, 0], z[:, 0, 1], z[:, 1, 0], z[:, 1, 1]
    zdiff = z11 - z12 - z21 + z22
    freq = nw.frequency.f
    omega = freq * 2 * math.pi
    return freq, zdiff.real, zdiff.imag / omega, zdiff.imag / zdiff.real  # freq, R, L, Q


def max_delta_linear(fa, xa, fb, xb):
    common = np.intersect1d(fa, fb)
    if common.size == 0:
        return None
    ia = np.searchsorted(fa, common)
    ib = np.searchsorted(fb, common)
    return float(np.max(np.abs(xb[ib] - xa[ia])))


def delta_db_at_freq(fa, xa, fb, xb, freq_hz):
    ia = int(np.argmin(np.abs(fa - freq_hz)))
    ib = int(np.argmin(np.abs(fb - freq_hz)))
    if abs(fa[ia] - freq_hz) > 0.6e9 or abs(fb[ib] - freq_hz) > 0.6e9:
        return None
    return float(abs(db(xb[ib]) - db(xa[ia])))


def value_at_freq(freq, values, freq_hz):
    idx = int(np.argmin(np.abs(freq - freq_hz)))
    if abs(freq[idx] - freq_hz) > 0.6e9:
        return None
    return float(values[idx])


def find_srf_hz(freq, Ldiff):
    """Frequency where the differential inductance crosses zero (self-resonance) -
    same method as mesh_convergence_inductor/results/plot_inductor_convergence.py."""
    idx = np.where(np.diff(np.sign(Ldiff)))[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    f0, f1 = freq[i], freq[i + 1]
    l0, l1 = Ldiff[i], Ldiff[i + 1]
    return f0 - l0 * (f1 - f0) / (l1 - l0)


def main():
    loaded = {}
    labels = {}
    networks = {}
    for entry in SERIES:
        result = load(entry)
        if result is None:
            print(f"WARNING: missing {entry[2]}, skipping")
            continue
        key, label, nw = result
        networks[key] = nw
        loaded[key] = (nw.frequency.f, s_traces(nw))
        labels[key] = label

    if len(loaded) < 2:
        print("Need at least two results; exiting.")
        return

    os.makedirs(PLOT_DIR, exist_ok=True)

    # ---------- S-parameter delta table ----------
    def fmt(x):
        return f"{x:.4f}" if x is not None else "n/a"

    csv_path = os.path.join(HERE, "results", "delta_S_table.csv") if os.path.basename(HERE) != "results" else os.path.join(HERE, "delta_S_table.csv")
    csv_path = os.path.join(HERE, "delta_S_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param", "Comparison", "What changes", "Max|dS| (linear)"] +
                         [f"|dS_dB| at {g}GHz" for g in EVAL_FREQS_GHZ])
        for pname in PARAMS:
            for key_a, key_b, what in COMPARISONS:
                if key_a not in loaded or key_b not in loaded:
                    continue
                fa, xa = loaded[key_a][0], loaded[key_a][1][pname]
                fb, xb = loaded[key_b][0], loaded[key_b][1][pname]
                max_d = max_delta_linear(fa, xa, fb, xb)
                d_vals = [delta_db_at_freq(fa, xa, fb, xb, g * 1e9) for g in EVAL_FREQS_GHZ]
                writer.writerow([pname, f"{labels[key_a]} -> {labels[key_b]}", what,
                                  fmt(max_d)] + [fmt(d) for d in d_vals])
    print(f"Wrote delta-S table: {csv_path}")

    # ---------- S-parameter overlay plots ----------
    colors = {"surface_2um": "#4c72b0", "volume_2um": "#dd8452", "volume_1um": "#c44e52"}
    styles = {"surface_2um": "-", "volume_2um": "--", "volume_1um": "-"}

    for pname in PARAMS:
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for key, _label, _fname in SERIES:
            if key not in loaded:
                continue
            freq, pdict = loaded[key]
            freq_ghz = freq / 1e9
            ax_mag.plot(freq_ghz, db(pdict[pname]), color=colors[key], linestyle=styles[key], label=labels[key])
            ax_phase.plot(freq_ghz, deg(pdict[pname]), color=colors[key], linestyle=styles[key], label=labels[key])
        ax_mag.set_ylabel(f"|{pname}| (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.legend(fontsize=8)
        ax_mag.set_title(f"{pname}: surface-impedance vs. filled_metals conductor modeling")
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel(f"arg({pname}) (deg)")
        ax_phase.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{pname.lower()}_comparison.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")

    # ---------- differential L/Q/Rseries ----------
    diff_traces = {}
    for key, (label, _fname) in {k: (labels[k], None) for k in loaded}.items():
        freq, R, L, Q = get_diff_model(networks[key])
        diff_traces[key] = dict(label=label, freq=freq, R=R, L=L, Q=Q)

    # cap the plotted range below self-resonance (L flips sign past SRF, not
    # meaningful as "the inductance" there) - use the finest variant's own SRF
    ref_key = "volume_1um" if "volume_1um" in diff_traces else list(diff_traces.keys())[-1]
    srf_hz = find_srf_hz(diff_traces[ref_key]["freq"], diff_traces[ref_key]["L"])
    fmax_ghz = 1.2 * srf_hz / 1e9 if srf_hz else max(tr["freq"].max() for tr in diff_traces.values()) / 1e9
    srf_note = f" (SRF~{srf_hz/1e9:.1f} GHz)" if srf_hz else ""

    param_info = {
        "L": ("Diff. Inductance (nH)", "Differential inductance", 1e9),
        "Q": ("Diff. Q factor", "Differential Q factor", 1),
        "R": ("Diff. series resistance (Ohm)", "Differential series resistance", 1),
    }
    for pname, (ylabel, title, scale) in param_info.items():
        fig, ax = plt.subplots(figsize=(7, 5.5))
        for key, _label, _fname in SERIES:
            if key not in diff_traces:
                continue
            tr = diff_traces[key]
            freq_ghz = tr["freq"] / 1e9
            mask = freq_ghz <= fmax_ghz
            ax.plot(freq_ghz[mask], (tr[pname] * scale)[mask], color=colors[key], linestyle=styles[key], label=tr["label"])
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel(ylabel)
        ax.set_xlim(0, fmax_ghz)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"{title}: surface-impedance vs. filled_metals{srf_note}")
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"inductor_LQR_{pname.lower()}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")

    # ---------- L/Q/R delta table ----------
    lqr_csv = os.path.join(HERE, "delta_LQR_table.csv")
    with open(lqr_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Freq (GHz)", "Variant", "L (nH)", "Q", "Rseries (Ohm)"])
        for g in EVAL_FREQS_GHZ:
            for key, _label, _fname in SERIES:
                if key not in diff_traces:
                    continue
                tr = diff_traces[key]
                L_val = value_at_freq(tr["freq"], tr["L"], g * 1e9)
                Q_val = value_at_freq(tr["freq"], tr["Q"], g * 1e9)
                R_val = value_at_freq(tr["freq"], tr["R"], g * 1e9)
                writer.writerow([f"{g:.1f}", tr["label"],
                                  fmt(L_val * 1e9) if L_val is not None else "n/a",
                                  fmt(Q_val) if Q_val is not None else "n/a",
                                  fmt(R_val) if R_val is not None else "n/a"])
    print(f"Wrote L/Q/R table: {lqr_csv}")


if __name__ == "__main__":
    main()
