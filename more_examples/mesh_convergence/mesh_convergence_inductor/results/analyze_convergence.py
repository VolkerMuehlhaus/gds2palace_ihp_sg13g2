#!/usr/bin/env python
"""Mesh convergence analysis for the ind_frame spiral inductor (2-port).

Reads de-embedded 2-port Touchstone files from results/snp/, computes
delta-S tables and overlay plots across mesh variants (order=2 uniform
sweep + AMR), following the same convention as the balun and transformer
mesh convergence studies: Max|dS| is the linear complex-magnitude
difference over the common frequency band; dB readouts are given at a
few representative frequencies.

S12 is not shown separately (S12==S21 by reciprocity for this passive
2-port); only S11, S21, S22 are analyzed.
"""
import os
import csv
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")

UNIFORM_SERIES = [
    ("mesh5", "5 um (uniform)", "ind_frame_mesh5.s2p"),
    ("mesh3", "3 um (uniform)", "ind_frame_mesh3.s2p"),
    ("mesh2", "2 um (uniform)", "ind_frame_mesh2.s2p"),
    ("mesh1", "1 um (uniform)", "ind_frame_mesh1.s2p"),
]
AMR_ENTRY = ("amr2", "AMR (5 um start, 2 it.)", "ind_frame_amr2_final.s2p")

EVAL_FREQS_GHZ = [1, 25, 50]  # sweep edges + midpoint, matches the 0-50 GHz sweep


def load(entry):
    key, label, fname = entry
    path = os.path.join(SNP_DIR, fname)
    if not os.path.isfile(path):
        return None
    nw = rf.Network(path)
    nw.name = label
    return key, label, nw


def db(x):
    return 20 * np.log10(np.abs(x))


def deg(x):
    return np.angle(x, deg=True)


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


PARAMS = ["S11", "S21", "S22"]


def s_traces(nw):
    s = nw.s
    return {"S11": s[:, 0, 0], "S21": s[:, 1, 0], "S22": s[:, 1, 1]}


def main():
    loaded = []
    for entry in UNIFORM_SERIES:
        result = load(entry)
        if result:
            loaded.append(result)
        else:
            print(f"WARNING: missing {entry[2]}, skipping")
    amr_result = load(AMR_ENTRY)

    if len(loaded) < 2:
        print("Need at least two uniform-mesh results; exiting.")
        return

    traces = {}
    for key, label, nw in loaded + ([amr_result] if amr_result else []):
        traces[key] = (nw.frequency.f, s_traces(nw))

    def fmt(x):
        return f"{x:.4f}" if x is not None else "n/a"

    comparisons = [(loaded[i - 1], loaded[i]) for i in range(1, len(loaded))]
    if amr_result:
        comparisons.append((loaded[-1], amr_result))

    csv_path = os.path.join(HERE, "delta_S_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param", "Comparison", "Max|dS| (linear)"] +
                         [f"|dS_dB| at {f}GHz" for f in EVAL_FREQS_GHZ])
        for pname in PARAMS:
            for (key_a, label_a, _), (key_b, label_b, _) in comparisons:
                fa, xa = traces[key_a][0], traces[key_a][1][pname]
                fb, xb = traces[key_b][0], traces[key_b][1][pname]
                max_d = max_delta_linear(fa, xa, fb, xb)
                d_vals = [delta_db_at_freq(fa, xa, fb, xb, f * 1e9) for f in EVAL_FREQS_GHZ]
                writer.writerow([pname, f"{label_a} -> {label_b}", fmt(max_d)] + [fmt(d) for d in d_vals])
    print(f"Wrote delta-S table: {csv_path}")

    ref_key, ref_label, _ = loaded[-1]
    vs_finest = list(loaded[:-1])
    if amr_result:
        vs_finest.append(amr_result)

    csv_path_ref = os.path.join(HERE, "delta_S_vs_finest.csv")
    with open(csv_path_ref, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param", "Mesh", f"Max|dS| vs. {ref_label} (linear)"] +
                         [f"|dS_dB| at {f}GHz" for f in EVAL_FREQS_GHZ])
        for pname in PARAMS:
            for key, label, _ in vs_finest:
                fa, xa = traces[key][0], traces[key][1][pname]
                fb, xb = traces[ref_key][0], traces[ref_key][1][pname]
                max_d = max_delta_linear(fa, xa, fb, xb)
                d_vals = [delta_db_at_freq(fa, xa, fb, xb, f * 1e9) for f in EVAL_FREQS_GHZ]
                writer.writerow([pname, label, fmt(max_d)] + [fmt(d) for d in d_vals])
    print(f"Wrote delta-S-vs-finest table: {csv_path_ref}")

    os.makedirs(PLOT_DIR, exist_ok=True)
    colors = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b2", "#937860"]
    all_keys = [k for k, _, _ in loaded] + (["amr2"] if amr_result else [])
    all_labels = {k: l for k, l, _ in loaded}
    if amr_result:
        all_labels[amr_result[0]] = amr_result[1]

    for pname in PARAMS:
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for idx, key in enumerate(all_keys):
            freq, pdict = traces[key]
            color = colors[idx % len(colors)]
            style = "--" if key == "amr2" else "-"
            freq_ghz = freq / 1e9
            ax_mag.plot(freq_ghz, db(pdict[pname]), color=color, linestyle=style, label=all_labels[key])
            ax_phase.plot(freq_ghz, deg(pdict[pname]), color=color, linestyle=style, label=all_labels[key])
        ax_mag.set_ylabel(f"|{pname}| (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.legend(fontsize=8)
        ax_mag.set_title(f"{pname} vs. mesh refinement")
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel(f"arg({pname}) (deg)")
        ax_phase.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{pname.lower()}_convergence.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")


if __name__ == "__main__":
    main()
