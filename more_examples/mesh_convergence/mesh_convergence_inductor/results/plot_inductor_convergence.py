#!/usr/bin/env python
"""Inductance / Q-factor / resistance convergence for the ind_frame spiral
inductor, evaluated the same way as D:\\github\\plot_inductor\\plot_inductor.py:
2-port S-parameters -> differential Z (Zdiff = Z11-Z12-Z21+Z22) -> Ldiff =
Im(Zdiff)/omega, Qdiff = Im(Zdiff)/Re(Zdiff), Rdiff = Re(Zdiff).

Reads de-embedded 2-port Touchstone files from results/snp/ for the uniform
mesh sweep (order=2), the AMR final result, and the order=1 comparison
sweep, then produces:
  - separate overlay plots of L, Q, R vs. frequency across the order=2 mesh
    sweep + AMR
  - a delta table (L, Q) vs. the finest order=2 mesh, at a few frequencies
  - an order=1 vs order=2 overlay (same cell sizes) to show what accuracy is
    given up for the order=1 speed-up (see order_comparison.py for timing)
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

# order=2 uniform mesh sweep (finest last, for reference)
UNIFORM_SERIES = [
    ("mesh5", "5 um (uniform)", "ind_frame_mesh5.s2p"),
    ("mesh3", "3 um (uniform)", "ind_frame_mesh3.s2p"),
    ("mesh2", "2 um (uniform)", "ind_frame_mesh2.s2p"),
    ("mesh1", "1 um (uniform)", "ind_frame_mesh1.s2p"),
]
AMR_ENTRY = ("amr2", "AMR (5 um start, 2 it.)", "ind_frame_amr2_final.s2p")

# order=1 comparison sweep (same cell sizes as a subset of the order=2 sweep)
ORDER1_SERIES = [
    ("mesh3_order1", "3 um, order 1", "ind_frame_mesh3_order1.s2p"),
    ("mesh2_order1", "2 um, order 1", "ind_frame_mesh2_order1.s2p"),
    ("mesh1_order1", "1 um, order 1", "ind_frame_mesh1_order1.s2p"),
]

FMIN_HZ = 100e6  # avoid divide-by-zero near DC, same convention as plot_inductor.py

PARAM_INFO = {
    "L": ("Diff. Inductance (nH)", "Differential inductance", 1e9),
    "Q": ("Diff. Q factor", "Differential Q factor", 1),
    "R": ("Diff. Resistance (Ohm)", "Differential resistance", 1),
}


def load(fname):
    path = os.path.join(SNP_DIR, fname)
    if not os.path.isfile(path):
        return None
    return rf.Network(path)


def get_diff_model(nw):
    z = nw.z
    z11, z12, z21, z22 = z[:, 0, 0], z[:, 0, 1], z[:, 1, 0], z[:, 1, 1]
    zdiff = z11 - z12 - z21 + z22
    freq = nw.frequency.f
    omega = freq * 2 * math.pi
    Ldiff = zdiff.imag / omega
    Rdiff = zdiff.real
    Qdiff = zdiff.imag / zdiff.real
    return freq, Rdiff, Ldiff, Qdiff


def restrict(nw, fmin, fmax):
    fspec = f"{int(fmin/1e6)}-{int(fmax/1e6)}mhz"
    return nw[fspec]


def find_srf_hz(freq, Ldiff):
    """Frequency where the differential inductance crosses zero (self-resonance)."""
    idx = np.where(np.diff(np.sign(Ldiff)))[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    f0, f1 = freq[i], freq[i + 1]
    l0, l1 = Ldiff[i], Ldiff[i + 1]
    return f0 - l0 * (f1 - f0) / (l1 - l0)


def load_series(series):
    loaded = []
    for key, label, fname in series:
        nw = load(fname)
        if nw is None:
            print(f"WARNING: missing {fname}, skipping")
            continue
        fmax = nw.frequency.f.max()
        nw = restrict(nw, FMIN_HZ, fmax)
        loaded.append((key, label, nw))
    return loaded


def build_traces(loaded, amr_entry):
    traces = {}
    for key, label, nw in loaded:
        freq, Rdiff, Ldiff, Qdiff = get_diff_model(nw)
        traces[key] = dict(label=label, freq=freq, R=Rdiff, L=Ldiff, Q=Qdiff)

    amr_trace = None
    if amr_entry is not None:
        amr_nw = load(amr_entry[2])
        if amr_nw is not None:
            fmax = amr_nw.frequency.f.max()
            amr_nw = restrict(amr_nw, FMIN_HZ, fmax)
            freq, Rdiff, Ldiff, Qdiff = get_diff_model(amr_nw)
            amr_trace = dict(label=amr_entry[1], freq=freq, R=Rdiff, L=Ldiff, Q=Qdiff)
    return traces, amr_trace


def plot_series(loaded, amr_entry, title_suffix, out_prefix, fmax_ghz=None):
    """Separate overlay plots (one PNG each) of L, Q, R vs frequency."""
    traces, amr_trace = build_traces(loaded, amr_entry)

    if not traces and amr_trace is None:
        print(f"No data for {out_prefix}, skipping plots")
        return None

    ref = list(traces.values())[-1] if traces else amr_trace
    srf_hz = find_srf_hz(ref["freq"], ref["L"])
    if fmax_ghz is None:
        if srf_hz is not None:
            fmax_ghz = 1.2 * srf_hz / 1e9
        else:
            fmax_ghz = ref["freq"].max() / 1e9

    colors = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b2", "#937860"]
    all_traces = list(traces.values()) + ([amr_trace] if amr_trace else [])
    all_keys = list(traces.keys()) + (["amr"] if amr_trace else [])

    srf_note = f" (SRF~{srf_hz/1e9:.2f} GHz)" if srf_hz else ""

    for pname, (ylabel, title, scale) in PARAM_INFO.items():
        fig, ax = plt.subplots(figsize=(7, 5.5))
        for idx, (key, tr) in enumerate(zip(all_keys, all_traces)):
            color = colors[idx % len(colors)]
            style = "--" if key == "amr" or key.endswith("_order1") else "-"
            freq_ghz = tr["freq"] / 1e9
            mask = freq_ghz <= fmax_ghz
            ax.plot(freq_ghz[mask], tr[pname][mask] * scale, color=color, linestyle=style, label=tr["label"])
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel(ylabel)
        ax.set_xlim(0, fmax_ghz)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"{title} {title_suffix}{srf_note}")
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{out_prefix}_{pname.lower()}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")

    return dict(traces=traces, amr=amr_trace, srf_hz=srf_hz, fmax_ghz=fmax_ghz)


def delta_table(loaded, amr_entry, eval_freqs_ghz, out_csv):
    traces = {}
    for key, label, nw in loaded:
        freq, Rdiff, Ldiff, Qdiff = get_diff_model(nw)
        traces[key] = dict(label=label, freq=freq, L=Ldiff, Q=Qdiff)
    if amr_entry is not None:
        amr_nw = load(amr_entry[2])
        if amr_nw is not None:
            fmax = amr_nw.frequency.f.max()
            amr_nw = restrict(amr_nw, FMIN_HZ, fmax)
            freq, Rdiff, Ldiff, Qdiff = get_diff_model(amr_nw)
            traces["amr"] = dict(label=amr_entry[1], freq=freq, L=Ldiff, Q=Qdiff)

    if len(traces) < 2:
        print("Not enough data for delta table, skipping")
        return

    ref_key = list(traces.keys())[len(loaded) - 1] if loaded else list(traces.keys())[-1]  # finest uniform mesh
    ref = traces[ref_key]

    rows = []
    for f_ghz in eval_freqs_ghz:
        for key, tr in traces.items():
            if key == ref_key:
                continue
            fa = tr["freq"]
            fb = ref["freq"]
            ia = int(np.argmin(np.abs(fa - f_ghz * 1e9)))
            ib = int(np.argmin(np.abs(fb - f_ghz * 1e9)))
            if abs(fa[ia] - f_ghz * 1e9) > 0.6e9 or abs(fb[ib] - f_ghz * 1e9) > 0.6e9:
                continue
            dL_pct = 100 * (tr["L"][ia] - ref["L"][ib]) / ref["L"][ib] if ref["L"][ib] else float("nan")
            dQ_pct = 100 * (tr["Q"][ia] - ref["Q"][ib]) / ref["Q"][ib] if ref["Q"][ib] else float("nan")
            rows.append([f"{f_ghz:.1f}", tr["label"], f"{tr['L'][ia]*1e9:.4f}", f"{ref['L'][ib]*1e9:.4f}",
                         f"{dL_pct:+.2f}", f"{tr['Q'][ia]:.2f}", f"{ref['Q'][ib]:.2f}", f"{dQ_pct:+.2f}"])

    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Freq (GHz)", "Mesh", "L (nH)", f"L_ref ({ref['label']}) (nH)", "dL (%)",
                          "Q", f"Q_ref ({ref['label']})", "dQ (%)"])
        writer.writerows(rows)
    print(f"Wrote delta table: {out_csv}")


def main():
    os.makedirs(PLOT_DIR, exist_ok=True)

    uniform_loaded = load_series(UNIFORM_SERIES)
    order1_loaded = load_series(ORDER1_SERIES)

    if uniform_loaded:
        result = plot_series(uniform_loaded, AMR_ENTRY, "vs. mesh (order 2)", "inductor_LQR_convergence")
        if result:
            eval_freqs = [1.0, 10.0, 25.0]
            if result["srf_hz"]:
                eval_freqs.append(round(result["srf_hz"] / 1e9 * 0.9, 1))
            delta_table(uniform_loaded, AMR_ENTRY, sorted(set(eval_freqs)),
                        os.path.join(HERE, "delta_LQ_table.csv"))

    # order1 vs order2 overlay at matching cell sizes
    matching_order2 = [(k, l, nw) for k, l, nw in uniform_loaded if k in {"mesh1", "mesh2", "mesh3"}]
    combined = matching_order2 + order1_loaded
    if combined:
        plot_series(combined, None, "order 1 vs order 2 (matching cell sizes)", "inductor_LQR_order_comparison")


if __name__ == "__main__":
    main()
