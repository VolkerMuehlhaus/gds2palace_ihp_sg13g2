#!/usr/bin/env python
"""Mesh convergence analysis for trans_100diff_to_80se_ports (3-port MIM-
loaded balun: port 1 single-ended, ports 2/3 a differential pair).

Uniform mesh sweep at refined_cellsize = 3 (the initial baseline check), 2,
1 um (order 2) plus AMR (2 iterations, starting mesh 2 um) -- no order=1
comparison for this study. Metal3 is pinned to a fixed 5 um refined_cellsize
in every variant (refined_cellsize_override), independent of the swept
global cell size, and merge_polygon_size=3um (TopVia2 array merging) is
identical across all variants -- so the 3um baseline run is directly
comparable to the mesh2/mesh1/amr2 sweep despite predating it.

Uses the RAW (non-de-embedded) Touchstone files throughout, not the
port-inductance-de-embedded ones -- same convention as the baseline
analysis in analyze_baseline.py, so the whole report stays internally
consistent.

Mixed-mode reduction (single-ended port 1 <-> differential mode of ports
2/3, at the true Z01=80 ohm / Z02=100 ohm system impedances) is the same
one documented in analyze_baseline.py -- see that file for the derivation.
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
    ("mesh3", "3 um (uniform, initial check)", "trans_100diff_to_80se_ports.s3p"),
    ("mesh2", "2 um (uniform)", "trans_100diff_to_80se_ports_mesh2.s3p"),
    ("mesh1", "1 um (uniform)", "trans_100diff_to_80se_ports_mesh1.s3p"),
]
AMR_ENTRY = ("amr2", "AMR (2 um start, 2 it.)", "trans_100diff_to_80se_ports_amr2.s3p")

Z01 = 80.0   # true single-ended external system impedance (port 1)
Z02 = 100.0  # true differential external system impedance (ports 2/3)

EVAL_FREQS_GHZ = [17, 19.5, 22]  # band edges + center

PARAMS = ["Sss11", "Sds21", "Sdd22"]


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


def mixed_mode_traces(nw, z01=Z01, z02=Z02):
    Z = nw.z
    Zaa = Z[:, 0, 0]
    Zab = Z[:, 0, 1] - Z[:, 0, 2]
    Zba = Z[:, 1, 0] - Z[:, 2, 0]
    Zbb = Z[:, 1, 1] - Z[:, 1, 2] - Z[:, 2, 1] + Z[:, 2, 2]
    D = (Zaa + z01) * (Zbb + z02) - Zab * Zba
    Sss11 = ((Zaa - z01) * (Zbb + z02) - Zab * Zba) / D
    Sdd22 = ((Zaa + z01) * (Zbb - z02) - Zab * Zba) / D
    Sds21 = 2 * Zba * np.sqrt(z01 * z02) / D
    return {"Sss11": Sss11, "Sds21": Sds21, "Sdd22": Sdd22}


def true_z_single_ended(nw, z01=Z01):
    """Renormalize to the true system impedance per physical port: port 1
    (single-ended) to z01, ports 2/3 left at 50 ohm each -- the natural
    per-leg reference for a 100 ohm differential pair with equal legs
    (Zdiff = 2*50). Returns raw S21, S31 (port1->port2, port1->port3)."""
    nw2 = nw.copy()
    nw2.renormalize([z01, 50.0, 50.0])
    return nw2.s[:, 1, 0], nw2.s[:, 2, 0]


def amplitude_imbalance_db(nw, z01=Z01):
    s21, s31 = true_z_single_ended(nw, z01)
    return db(s21) - db(s31)


def phase_difference_centered(nw, z01=Z01, center_deg=180.0):
    """Phase(S21)-Phase(S31), unwrapped along frequency to avoid the raw
    +/-180 wraparound artifact, then shifted by a whole number of 360 deg
    turns so the trace sits near center_deg (the physically expected value
    for a balun's two antiphase differential outputs)."""
    s21, s31 = true_z_single_ended(nw, z01)
    ratio = s21 / s31
    phase_deg = np.unwrap(np.angle(ratio)) * 180.0 / np.pi
    shift = np.round((center_deg - np.mean(phase_deg)) / 360.0) * 360.0
    return phase_deg + shift


def value_at_freq(freq, x, freq_hz):
    i = int(np.argmin(np.abs(freq - freq_hz)))
    return x[i] if abs(freq[i] - freq_hz) < 0.06e9 else None


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
    if abs(fa[ia] - freq_hz) > 0.06e9 or abs(fb[ib] - freq_hz) > 0.06e9:
        return None
    return float(abs(db(xb[ib]) - db(xa[ia])))


def main():
    loaded = []
    for entry in UNIFORM_SERIES:
        result = load(entry)
        if result:
            loaded.append(result)
        else:
            print(f"WARNING: missing {entry[2]}, skipping")
    amr_result = load(AMR_ENTRY)
    if not amr_result:
        print(f"WARNING: missing {AMR_ENTRY[2]}")

    if len(loaded) < 2:
        print("Need at least two uniform-mesh results; exiting.")
        return

    traces = {}
    for key, label, nw in loaded + ([amr_result] if amr_result else []):
        traces[key] = (nw.frequency.f, mixed_mode_traces(nw))

    def fmt(x):
        return f"{x:.4f}" if x is not None else "n/a"

    comparisons = [(loaded[i - 1], loaded[i]) for i in range(1, len(loaded))]
    if amr_result:
        comparisons.append((loaded[-1], amr_result))

    csv_path = os.path.join(HERE, "delta_S_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param", "Comparison", "Max|dS| (linear)"] +
                         [f"|dS_dB| at {fg}GHz" for fg in EVAL_FREQS_GHZ])
        for pname in PARAMS:
            for (key_a, label_a, _), (key_b, label_b, _) in comparisons:
                fa, xa = traces[key_a][0], traces[key_a][1][pname]
                fb, xb = traces[key_b][0], traces[key_b][1][pname]
                max_d = max_delta_linear(fa, xa, fb, xb)
                d_vals = [delta_db_at_freq(fa, xa, fb, xb, fg * 1e9) for fg in EVAL_FREQS_GHZ]
                writer.writerow([pname, f"{label_a} -> {label_b}", fmt(max_d)] + [fmt(d) for d in d_vals])
    print(f"Wrote delta-S table: {csv_path}")

    if amr_result:
        ref_key, ref_label, _ = amr_result
        csv_path_ref = os.path.join(HERE, "delta_S_vs_finest.csv")
        with open(csv_path_ref, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Param", "Mesh", f"Max|dS| vs. {ref_label} (linear)"] +
                             [f"|dS_dB| at {fg}GHz" for fg in EVAL_FREQS_GHZ])
            for pname in PARAMS:
                for key, label, _ in loaded:
                    fa, xa = traces[key][0], traces[key][1][pname]
                    fb, xb = traces[ref_key][0], traces[ref_key][1][pname]
                    max_d = max_delta_linear(fa, xa, fb, xb)
                    d_vals = [delta_db_at_freq(fa, xa, fb, xb, fg * 1e9) for fg in EVAL_FREQS_GHZ]
                    writer.writerow([pname, label, fmt(max_d)] + [fmt(d) for d in d_vals])
        print(f"Wrote delta-S-vs-finest table: {csv_path_ref}")

    all_keys_for_mag = [k for k, _, _ in loaded] + (["amr2"] if amr_result else [])
    all_labels_for_mag = {k: l for k, l, _ in loaded}
    if amr_result:
        all_labels_for_mag[amr_result[0]] = amr_result[1]
    csv_path_mag = os.path.join(HERE, "s_parameter_magnitude_table.csv")
    with open(csv_path_mag, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param", "Mesh"] + [f"{fg} GHz |S| (dB)" for fg in EVAL_FREQS_GHZ])
        for pname in PARAMS:
            for key in all_keys_for_mag:
                freq, pdict = traces[key]
                x = pdict[pname]
                mags = [value_at_freq(freq, x, fg * 1e9) for fg in EVAL_FREQS_GHZ]
                row = [pname, all_labels_for_mag[key]] + [f"{db(v):.3f}" if v is not None else "n/a" for v in mags]
                writer.writerow(row)
    print(f"Wrote S-parameter magnitude table: {csv_path_mag}")

    os.makedirs(PLOT_DIR, exist_ok=True)
    colors = {"mesh3": "#8172b2", "mesh2": "#4c72b0", "mesh1": "#dd8452", "amr2": "#55a868"}
    all_keys = [k for k, _, _ in loaded] + (["amr2"] if amr_result else [])
    all_labels = {k: l for k, l, _ in loaded}
    if amr_result:
        all_labels[amr_result[0]] = amr_result[1]

    for pname in PARAMS:
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for key in all_keys:
            freq, pdict = traces[key]
            style = "--" if key == "amr2" else "-"
            freq_ghz = freq / 1e9
            ax_mag.plot(freq_ghz, db(pdict[pname]), color=colors[key], linestyle=style, label=all_labels[key])
            ax_phase.plot(freq_ghz, deg(pdict[pname]), color=colors[key], linestyle=style, label=all_labels[key])
        ax_mag.set_ylabel(f"|{pname}| (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.legend(fontsize=8)
        ax_mag.set_title(f"{pname} vs. mesh refinement (Z01={Z01:.0f} ohm SE, Z02={Z02:.0f} ohm diff)")
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel(f"arg({pname}) (deg)")
        ax_phase.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{pname.lower()}_convergence.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")

    # amplitude imbalance and phase difference between the two differential
    # outputs (S21, S31), at the true system impedance (port 1 -> 80 ohm,
    # ports 2/3 left at 50 ohm each -- the natural per-leg reference for the
    # 100 ohm differential pair)
    all_nws = {k: nw for k, _, nw in loaded}
    if amr_result:
        all_nws[amr_result[0]] = amr_result[2]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for key in all_keys:
        nw = all_nws[key]
        freq_ghz = nw.frequency.f / 1e9
        style = "--" if key == "amr2" else "-"
        ax.plot(freq_ghz, amplitude_imbalance_db(nw), color=colors[key], linestyle=style, label=all_labels[key])
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|S21| - |S31| (dB)")
    ax.set_title(f"Amplitude imbalance, port 2 vs. port 3 (true Z: port1={Z01:.0f} ohm, ports2/3=50 ohm each)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "amplitude_imbalance.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for key in all_keys:
        nw = all_nws[key]
        freq_ghz = nw.frequency.f / 1e9
        style = "--" if key == "amr2" else "-"
        ax.plot(freq_ghz, phase_difference_centered(nw), color=colors[key], linestyle=style, label=all_labels[key])
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Phase(S21) - Phase(S31) (deg)")
    ax.set_ylim(177, 183)
    ax.axhline(180, color="black", linewidth=0.8, alpha=0.5)
    ax.set_title(f"Phase difference, port 2 vs. port 3 (true Z: port1={Z01:.0f} ohm, ports2/3=50 ohm each)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "phase_difference.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")


if __name__ == "__main__":
    main()
