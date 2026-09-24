#!/usr/bin/env python
"""Mesh convergence analysis for the conformal-3D-passivation D-band balun study.

Reads the de-embedded Touchstone files collected in results/snp/ (this
study's own 4/2/1 um conformal-stackup points, and the matching 4/2/1 um
points from the sibling planar-stackup study), computes per-point and max
delta-S between successive mesh refinements for S11, S21, S31, writes CSV
tables, and renders overlay plots (magnitude + phase vs. frequency):
  - convergence within the conformal stackup (4 -> 2 -> 1 um)
  - conformal vs. planar stackup at each matching mesh size
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
PLANAR_SNP_DIR = os.path.join(
    HERE, "..", "..", "mesh_convergence", "mesh_convergence_D-band_balun", "results", "snp"
)

# ordered coarse -> fine
CONFORMAL_SERIES = [
    ("mesh4", "4 um (conformal)", "balun_conformal_mesh4um.s3p", SNP_DIR),
    ("mesh2", "2 um (conformal)", "balun_conformal_mesh2um.s3p", SNP_DIR),
    ("mesh1", "1 um (conformal)", "balun_conformal_mesh1um.s3p", SNP_DIR),
]
PLANAR_SERIES = [
    ("mesh4", "4 um (planar)", "balun_mesh4um.s3p", PLANAR_SNP_DIR),
    ("mesh2", "2 um (planar)", "balun_mesh2um.s3p", PLANAR_SNP_DIR),
    ("mesh1", "1 um (planar)", "balun_mesh1um.s3p", PLANAR_SNP_DIR),
]

SPARAMS = [(1, 1, "S11"), (2, 1, "S21"), (3, 1, "S31")]

COLORS = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b2", "#937860"]


def load(entry):
    key, label, fname, snp_dir = entry
    path = os.path.join(snp_dir, fname)
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

    Standard HFSS-style "Delta S" convergence metric (also used by
    palace_summary.py for AMR iterations, and the planar D-band-balun
    study). Deliberately NOT a dB(b)-dB(a) difference: near an
    S-parameter null a tiny absolute error produces a huge dB swing even
    though the physical mismatch is negligible.
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


DESIGN_FREQ_HZ = 155.0e9  # center of this balun's 140-170 GHz target band


def delta_db_at_freq(nw_a, nw_b, m, n, freq_hz):
    fa, fb = nw_a.frequency.f, nw_b.frequency.f
    ia = int(np.argmin(np.abs(fa - freq_hz)))
    ib = int(np.argmin(np.abs(fb - freq_hz)))
    if abs(fa[ia] - freq_hz) > 0.5e9 or abs(fb[ib] - freq_hz) > 0.5e9:
        return None
    return float(abs(db(nw_b.s[ib, m - 1, n - 1]) - db(nw_a.s[ia, m - 1, n - 1])))


def fmt(x):
    return f"{x:.4f}" if x is not None else "n/a"


def write_delta_table(csv_path, comparisons, ref_col_label):
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Param", "Comparison", f"Max|dS| (linear){ref_col_label}",
            "|dS_dB| at 100 GHz", "|dS_dB| at 155 GHz (design freq.)", "|dS_dB| at 200 GHz"
        ])
        for m, n, pname in SPARAMS:
            for label_a, nw_a, label_b, nw_b in comparisons:
                comparison = f"{label_a} -> {label_b}"
                max_d = max_delta_linear(nw_a, nw_b, m, n)
                d_lo, d_hi = band_edge_delta_db(nw_a, nw_b, m, n)
                d_design = delta_db_at_freq(nw_a, nw_b, m, n, DESIGN_FREQ_HZ)
                writer.writerow([pname, comparison, fmt(max_d), fmt(d_lo), fmt(d_design), fmt(d_hi)])
    print(f"Wrote table: {csv_path}")


def overlay_plot(series, out_name, title_suffix):
    os.makedirs(PLOT_DIR, exist_ok=True)
    for m, n, pname in SPARAMS:
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for idx, (key, label, nw) in enumerate(series):
            color = COLORS[idx % len(COLORS)]
            style = "--" if "planar" in label else "-"
            freq_ghz = nw.frequency.f / 1e9
            ax_mag.plot(freq_ghz, db(nw.s[:, m - 1, n - 1]), color=color, linestyle=style, label=label)
            ax_phase.plot(freq_ghz, deg(nw.s[:, m - 1, n - 1]), color=color, linestyle=style, label=label)
        ax_mag.set_ylabel(f"|{pname}| (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.legend(fontsize=8)
        ax_mag.set_title(f"{pname} {title_suffix}")
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel(f"arg({pname}) (deg)")
        ax_phase.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{pname.lower()}_{out_name}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")


def main():
    conformal = [r for r in (load(e) for e in CONFORMAL_SERIES) if r]
    planar = [r for r in (load(e) for e in PLANAR_SERIES) if r]

    missing_c = [e[2] for e in CONFORMAL_SERIES if not os.path.isfile(os.path.join(e[3], e[2]))]
    missing_p = [e[2] for e in PLANAR_SERIES if not os.path.isfile(os.path.join(e[3], e[2]))]
    if missing_c:
        print("WARNING: missing conformal files:", missing_c)
    if missing_p:
        print("WARNING: missing planar baseline files:", missing_p)

    # ---------------- within-conformal-study convergence (4->2->1 um) ----------------
    comparisons = [
        (conformal[i - 1][1], conformal[i - 1][2], conformal[i][1], conformal[i][2])
        for i in range(1, len(conformal))
    ]
    write_delta_table(os.path.join(HERE, "delta_S_table.csv"), comparisons, "")

    ref_label, ref_nw = conformal[-1][1], conformal[-1][2]
    vs_finest = [(label, nw, ref_label, ref_nw) for _, label, nw in conformal[:-1]]
    write_delta_table(os.path.join(HERE, "delta_S_vs_finest.csv"), vs_finest, f" vs. {ref_label}")

    overlay_plot(conformal, "convergence", "vs. mesh refinement (conformal 3D-passivation stackup)")

    # ---------------- conformal vs. planar, at matching mesh sizes ----------------
    planar_by_key = {k: (k, label, nw) for k, label, nw in planar}
    matched_comparisons = []
    matched_series_per_mesh = {}
    for key, label, nw in conformal:
        if key in planar_by_key:
            pkey, plabel, pnw = planar_by_key[key]
            matched_comparisons.append((plabel, pnw, label, nw))
            matched_series_per_mesh[key] = [(pkey, plabel, pnw), (key, label, nw)]
    write_delta_table(os.path.join(HERE, "delta_S_vs_planar.csv"), matched_comparisons, " (conformal vs. planar)")

    # one overlay plot per matching mesh size, planar vs conformal
    for key in ("mesh4", "mesh2", "mesh1"):
        if key in matched_series_per_mesh:
            overlay_plot(
                matched_series_per_mesh[key],
                f"planar_vs_conformal_{key}",
                f"planar vs. conformal-passivation stackup ({key.replace('mesh', '')} um)",
            )

    # combined plot: finest mesh (1 um) of each stackup, all three S-params already
    # covered above via the mesh1 comparison plot -- kept as the primary reference.


if __name__ == "__main__":
    main()
