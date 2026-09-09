#!/usr/bin/env python
"""Mesh convergence analysis for the D-band balun (RupokDas) study.

Reads the de-embedded Touchstone files collected in results/snp/, computes
per-point and max delta-S between successive mesh refinements for S11, S21,
S23, writes a CSV table, and renders overlay plots (magnitude + phase vs.
frequency) for S11/S21/S23 across all mesh variants.
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

# ordered coarse -> fine, plus AMR result compared against the finest uniform mesh
UNIFORM_SERIES = [
    ("mesh5", "5 um (uniform)", "balun_mesh5um.s3p"),
    ("mesh4", "4 um (uniform)", "balun_mesh4um.s3p"),
    ("mesh3", "3 um (uniform)", "balun_mesh3um.s3p"),
    ("mesh2", "2 um (uniform)", "balun_mesh2um.s3p"),
    ("mesh1", "1 um (uniform)", "balun_mesh1um.s3p"),
]
AMR_ENTRY = ("amr5", "AMR (5 um start, 5 it.)", "balun_amr5_final.s3p")

SPARAMS = [(1, 1, "S11"), (2, 1, "S21"), (2, 3, "S23")]

COLORS = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b2", "#937860"]


def load(label_key):
    key, label, fname = label_key
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


def max_delta_linear(nw_a, nw_b, m, n):
    """Max |S(b) - S(a)| (linear complex magnitude) over common frequencies.

    This is the standard HFSS-style "Delta S" convergence metric (also used
    by palace_summary.py for AMR iterations). Deliberately NOT a dB(b)-dB(a)
    difference: near an S-parameter null (Sxx close to 0), a tiny absolute
    error produces a huge dB swing even though the physical mismatch is
    negligible -- the linear metric stays well-behaved there.
    """
    fa, fb = nw_a.frequency.f, nw_b.frequency.f
    common = np.intersect1d(fa, fb)
    if common.size == 0:
        return None
    ia = np.searchsorted(fa, common)
    ib = np.searchsorted(fb, common)
    sa = nw_a.s[ia, m - 1, n - 1]
    sb = nw_b.s[ib, m - 1, n - 1]
    return float(np.max(np.abs(sb - sa)))


def band_edge_delta_db(nw_a, nw_b, m, n):
    """|S_dB(b)-S_dB(a)| at the lowest and highest common frequency."""
    fa, fb = nw_a.frequency.f, nw_b.frequency.f
    common = np.intersect1d(fa, fb)
    if common.size == 0:
        return None, None
    lo, hi = common[0], common[-1]
    ia_lo, ib_lo = np.searchsorted(fa, lo), np.searchsorted(fb, lo)
    ia_hi, ib_hi = np.searchsorted(fa, hi), np.searchsorted(fb, hi)
    d_lo = abs(db(nw_b.s[ib_lo, m - 1, n - 1]) - db(nw_a.s[ia_lo, m - 1, n - 1]))
    d_hi = abs(db(nw_b.s[ib_hi, m - 1, n - 1]) - db(nw_a.s[ia_hi, m - 1, n - 1]))
    return float(d_lo), float(d_hi)


DESIGN_FREQ_HZ = 155.0e9  # center of this balun's actual 140-170 GHz target band (per its GDS filename)


def delta_db_at_freq(nw_a, nw_b, m, n, freq_hz):
    """|S_dB(b)-S_dB(a)| at the frequency point nearest freq_hz."""
    fa, fb = nw_a.frequency.f, nw_b.frequency.f
    ia = int(np.argmin(np.abs(fa - freq_hz)))
    ib = int(np.argmin(np.abs(fb - freq_hz)))
    if abs(fa[ia] - freq_hz) > 0.5e9 or abs(fb[ib] - freq_hz) > 0.5e9:
        return None
    return float(abs(db(nw_b.s[ib, m - 1, n - 1]) - db(nw_a.s[ia, m - 1, n - 1])))


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
        print("Need at least two uniform-mesh results to compute deltas; exiting.")
        return

    def fmt(x):
        return f"{x:.4f}" if x is not None else "n/a"

    # ---------------- delta-S table across successive uniform refinements ----------------
    # comparisons in refinement order, one block per S-parameter
    comparisons = [(loaded[i - 1], loaded[i]) for i in range(1, len(loaded))]
    if amr_result:
        comparisons.append((loaded[-1], amr_result))

    csv_path = os.path.join(HERE, "delta_S_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Param", "Comparison", "Max|dS| (linear)",
            "|dS_dB| at 100 GHz", "|dS_dB| at 155 GHz (design freq.)", "|dS_dB| at 200 GHz"
        ])
        for m, n, pname in SPARAMS:
            for (key_a, label_a, nw_a), (key_b, label_b, nw_b) in comparisons:
                comparison = f"{label_a} -> {label_b}"
                max_d = max_delta_linear(nw_a, nw_b, m, n)
                d_lo, d_hi = band_edge_delta_db(nw_a, nw_b, m, n)
                d_design = delta_db_at_freq(nw_a, nw_b, m, n, DESIGN_FREQ_HZ)
                writer.writerow([pname, comparison, fmt(max_d), fmt(d_lo), fmt(d_design), fmt(d_hi)])
    print(f"Wrote delta-S table: {csv_path}")

    # ---------------- delta-S table: every mesh vs. finest uniform mesh (1um) ----------------
    ref_key, ref_label, ref_nw = loaded[-1]
    vs_finest = [(key, label, nw) for key, label, nw in loaded[:-1]]
    if amr_result:
        vs_finest.append(amr_result)

    csv_path_ref = os.path.join(HERE, "delta_S_vs_finest.csv")
    with open(csv_path_ref, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Param", "Mesh", f"Max|dS| vs. {ref_label} (linear)",
            "|dS_dB| at 100 GHz", "|dS_dB| at 155 GHz (design freq.)", "|dS_dB| at 200 GHz"
        ])
        for m, n, pname in SPARAMS:
            for key, label, nw in vs_finest:
                max_d = max_delta_linear(nw, ref_nw, m, n)
                d_lo, d_hi = band_edge_delta_db(nw, ref_nw, m, n)
                d_design = delta_db_at_freq(nw, ref_nw, m, n, DESIGN_FREQ_HZ)
                writer.writerow([pname, label, fmt(max_d), fmt(d_lo), fmt(d_design), fmt(d_hi)])
    print(f"Wrote delta-S-vs-finest table: {csv_path_ref}")

    # ---------------- overlay plots: mag (dB) + phase per S-param ----------------
    os.makedirs(PLOT_DIR, exist_ok=True)
    all_series = list(loaded)
    if amr_result:
        all_series.append(amr_result)

    for m, n, pname in SPARAMS:
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for idx, (key, label, nw) in enumerate(all_series):
            color = COLORS[idx % len(COLORS)]
            style = "--" if key == "amr5" else "-"
            freq_ghz = nw.frequency.f / 1e9
            ax_mag.plot(freq_ghz, db(nw.s[:, m - 1, n - 1]), color=color, linestyle=style, label=label)
            ax_phase.plot(freq_ghz, deg(nw.s[:, m - 1, n - 1]), color=color, linestyle=style, label=label)
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
