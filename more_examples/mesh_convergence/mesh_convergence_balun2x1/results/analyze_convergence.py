#!/usr/bin/env python
"""Mesh convergence analysis for the balun2x1 edge-coupled balun (4-port,
no center tap). Local port order [1:primary+, 2:primary-, 3:secondary+,
4:secondary-] maps directly onto ports 1-4 (PP,PN,S1,S2) -- no port
elimination/dropping is needed here, unlike the 5-port transformer study.

This is a 2:1 turns-ratio balun with real intended system impedances of
Z01=200 ohm differential on the primary and Z02=50 ohm differential on
the secondary (200/50=4, matching the turns ratio squared) -- NOT the
naive 2x50=100 ohm value the raw port_Z0=50.0 single-ended ports would
suggest for a 1:1 structure. Mixed-mode Sdd11/Sdd21/Sdd22 below are
therefore computed at this real, asymmetric reference: the native 4-port
Z-matrix is reduced to the differential-equivalent 2-port
(Zaa,Zab,Zba,Zbb) by antisymmetric combination across each port pair,
then converted to S-parameters via the standard unequal-reference-
impedance 2-port Z->S formula (a real-valued, unambiguous conversion --
not a mixed-mode port-ordering ambiguity):

    Zaa = Z11-Z12-Z21+Z22   (primary)
    Zab = Z13-Z14-Z23+Z24
    Zba = Z31-Z32-Z41+Z42   (== Zab by reciprocity)
    Zbb = Z33-Z34-Z43+Z44

    D     = (Zaa+Z01)*(Zbb+Z02) - Zab*Zba
    Sdd11 = ((Zaa-Z01)*(Zbb+Z02) - Zab*Zba) / D
    Sdd22 = ((Zaa+Z01)*(Zbb-Z02) - Zab*Zba) / D
    Sdd21 = 2*Zba*sqrt(Z01*Z02) / D

(Sanity check: setting Z01=Z02=100 instead reproduces the naive uniform
Bockelman-Eisenstadt Sdd11=0.5*(S11-S12-S21+S22) etc. -- appropriate for
a 1:1 structure like the transformer study -- to within ~1e-4, confirming
this general formula before trusting it at the real Z01=200/Z02=50
asymmetric reference used here.)

See differential_input_impedance.py for the floating-load input
impedance under the same real 50 ohm secondary load, viewed at the same
200 ohm primary reference.

Reads de-embedded 4-port Touchstone files from results/snp/, computes
delta-S tables and overlay plots across mesh variants (order=2 uniform
sweep + AMR), following the same convention as the other mesh
convergence studies in this repo.
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
    ("mesh5", "5 um (uniform)", "balun2x1_mesh5.s4p"),
    ("mesh2", "2 um (uniform)", "balun2x1_mesh2.s4p"),
    ("mesh1", "1 um (uniform)", "balun2x1_mesh1.s4p"),
]
AMR_ENTRY = ("amr2", "AMR (5 um start, 2 it.)", "balun2x1_amr2_final.s4p")

EVAL_FREQS_GHZ = [1, 25, 50]  # sweep edges + midpoint, matches the 1-50 GHz sweep


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


PARAMS = ["Sdd11", "Sdd21", "Sdd22"]

Z01 = 200.0  # primary differential reference -- the balun's actual intended system impedance
Z02 = 50.0   # secondary differential reference -- the balun's actual intended system impedance


def sdd_traces(nw, z01=Z01, z02=Z02):
    Z = nw.z
    Zaa = Z[:, 0, 0] - Z[:, 0, 1] - Z[:, 1, 0] + Z[:, 1, 1]
    Zab = Z[:, 0, 2] - Z[:, 0, 3] - Z[:, 1, 2] + Z[:, 1, 3]
    Zba = Z[:, 2, 0] - Z[:, 2, 1] - Z[:, 3, 0] + Z[:, 3, 1]
    Zbb = Z[:, 2, 2] - Z[:, 2, 3] - Z[:, 3, 2] + Z[:, 3, 3]
    D = (Zaa + z01) * (Zbb + z02) - Zab * Zba
    Sdd11 = ((Zaa - z01) * (Zbb + z02) - Zab * Zba) / D
    Sdd22 = ((Zaa + z01) * (Zbb - z02) - Zab * Zba) / D
    Sdd21 = 2 * Zba * np.sqrt(z01 * z02) / D
    return {"Sdd11": Sdd11, "Sdd21": Sdd21, "Sdd22": Sdd22}


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
        traces[key] = (nw.frequency.f, sdd_traces(nw))

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
        ax_mag.set_title(f"{pname} vs. mesh refinement (Z01={Z01:.0f} ohm primary, Z02={Z02:.0f} ohm secondary)")
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
