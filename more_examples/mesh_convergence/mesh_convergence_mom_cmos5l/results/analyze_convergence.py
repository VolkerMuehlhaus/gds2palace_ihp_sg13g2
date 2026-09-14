#!/usr/bin/env python
"""Mesh convergence analysis for the c4_frame_ports MOM capacitor (2-port),
IHP SG13CMOS5L technology.

Reads raw (non-de-embedded) 2-port Touchstone files from results/snp/ for
six fixed-frequency (1 GHz) runs -- uniform mesh cell size 0.2/0.1/0.05 um,
each at Palace finite-element order 2 and order 3 -- plus one separate
0-50 GHz frequency-sweep run at the coarsest mesh (0.2 um, order 2) used
only to show C12 vs. frequency for documentation.

Two convergence metrics are reported, per the study brief:
  - C12, the port1-port2 mutual capacitance, extracted from the raw
    Y-parameters as C12 = -Im(Y12) / (2*pi*f).
  - Delta-S: the linear-magnitude difference of S11/S21/S22 between mesh
    variants (Max|dS| reduces to a single value here since each
    fixed-frequency run has only one frequency point) and in dB at 1 GHz.

No de-embedding is applied (raw S/Y-parameters only), and no Palace mesh
quality metrics (DOF, solve time, error estimates) are reported here --
only what is useful to explain the observed C12/S convergence.
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

# (key, label, filename, mesh_um, order)
ORDER2_SERIES = [
    ("mesh200_o2", "0.2 um, order 2", "c4_frame_ports_mesh200nm.s2p", 0.2, 2),
    ("mesh100_o2", "0.1 um, order 2", "c4_frame_ports_mesh100nm.s2p", 0.1, 2),
    ("mesh50_o2", "0.05 um, order 2", "c4_frame_ports_mesh50nm.s2p", 0.05, 2),
]
ORDER3_SERIES = [
    ("mesh200_o3", "0.2 um, order 3", "c4_frame_ports_mesh200nm_order3.s2p", 0.2, 3),
    ("mesh100_o3", "0.1 um, order 3", "c4_frame_ports_mesh100nm_order3.s2p", 0.1, 3),
    ("mesh50_o3", "0.05 um, order 3", "c4_frame_ports_mesh50nm_order3.s2p", 0.05, 3),
]
ALL_FIXED = ORDER2_SERIES + ORDER3_SERIES

# mesh label -> (order2 key, order3 key), for the order-comparison table
ORDER_PAIRS = [
    ("0.2 um", "mesh200_o2", "mesh200_o3"),
    ("0.1 um", "mesh100_o2", "mesh100_o3"),
    ("0.05 um", "mesh50_o2", "mesh50_o3"),
]

SWEEP_ENTRY = ("mesh200_sweep", "0.2 um, order 2, 0-50 GHz sweep", "c4_frame_ports_mesh200nm_sweep.s2p")

FIXED_FREQ_GHZ = 1.0
PARAMS = ["S11", "S21", "S22"]


def load(fname):
    path = os.path.join(SNP_DIR, fname)
    if not os.path.isfile(path):
        return None
    return rf.Network(path)


def db(x):
    return 20 * np.log10(np.abs(x))


def s_traces(nw):
    s = nw.s
    return {"S11": s[:, 0, 0], "S21": s[:, 1, 0], "S22": s[:, 1, 1]}


def c12_from_y(nw):
    """Mutual (coupling) capacitance between port 1 and port 2, in farad,
    from the raw Y-parameters: C12 = -Im(Y12) / (2*pi*f)."""
    f = nw.frequency.f
    y12 = nw.y[:, 0, 1]
    return -np.imag(y12) / (2 * np.pi * f)


def fmt(x, digits=4):
    return f"{x:.{digits}f}" if x is not None else "n/a"


def load_series(series):
    loaded = {}
    for key, label, fname, mesh_um, order in series:
        nw = load(fname)
        if nw is None:
            print(f"WARNING: missing {fname}, skipping")
            continue
        loaded[key] = {"label": label, "nw": nw, "mesh_um": mesh_um, "order": order,
                        "s": s_traces(nw), "c12": c12_from_y(nw)[0]}
    return loaded


def main():
    data = load_series(ALL_FIXED)
    if len(data) < 2:
        print("Need at least two fixed-frequency results; exiting.")
        return

    os.makedirs(PLOT_DIR, exist_ok=True)

    # ---------------------------------------------------------------
    # 1) C12 convergence table (both orders), successive-mesh and
    #    vs-finest-mesh, within each order series.
    # ---------------------------------------------------------------
    cap_csv = os.path.join(HERE, "capacitance_convergence.csv")
    with open(cap_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Order", "Mesh (um)", "C12 (fF)",
                          "Delta vs next-finer (fF)", "Delta vs next-finer (%)",
                          "Delta vs finest same order (fF)", "Delta vs finest same order (%)"])
        for series in (ORDER2_SERIES, ORDER3_SERIES):
            keys = [k for k, *_ in series if k in data]
            if not keys:
                continue
            finest_key = keys[-1]
            c_finest = data[finest_key]["c12"] * 1e15
            for i, key in enumerate(keys):
                c = data[key]["c12"] * 1e15
                order = data[key]["order"]
                mesh_um = data[key]["mesh_um"]
                if i + 1 < len(keys):
                    c_next = data[keys[i + 1]]["c12"] * 1e15
                    d_next = c_next - c
                    d_next_pct = 100.0 * d_next / c
                else:
                    d_next = None
                    d_next_pct = None
                d_fin = c - c_finest
                d_fin_pct = 100.0 * d_fin / c_finest if c_finest else None
                writer.writerow([order, mesh_um, fmt(c),
                                  fmt(d_next), fmt(d_next_pct, 3),
                                  fmt(d_fin), fmt(d_fin_pct, 3)])
    print(f"Wrote capacitance convergence table: {cap_csv}")

    # ---------------------------------------------------------------
    # 2) Delta-S tables (successive-mesh and vs-finest), within each
    #    order series. Single frequency point -> Max|dS| (linear) and
    #    |dS_dB| at 1 GHz are the same comparison, shown together.
    # ---------------------------------------------------------------
    def s_deltas_csv(path, comparisons, label_col):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Param", label_col, "|dS| (linear)", f"|dS_dB| at {FIXED_FREQ_GHZ:g}GHz"])
            for pname in PARAMS:
                for label, key_a, key_b in comparisons:
                    xa = data[key_a]["s"][pname][0]
                    xb = data[key_b]["s"][pname][0]
                    d_lin = abs(xb - xa)
                    d_db = abs(db(np.array([xb]))[0] - db(np.array([xa]))[0])
                    writer.writerow([pname, label, fmt(d_lin, 6), fmt(d_db, 4)])
        print(f"Wrote: {path}")

    for order_name, series in (("order2", ORDER2_SERIES), ("order3", ORDER3_SERIES)):
        keys = [k for k, *_ in series if k in data]
        if len(keys) < 2:
            continue
        succ = [(f"{data[keys[i]]['label']} -> {data[keys[i+1]]['label']}", keys[i], keys[i + 1])
                for i in range(len(keys) - 1)]
        s_deltas_csv(os.path.join(HERE, f"delta_S_table_{order_name}.csv"), succ, "Comparison")

        finest = keys[-1]
        vs_fin = [(data[k]["label"], k, finest) for k in keys[:-1]]
        s_deltas_csv(os.path.join(HERE, f"delta_S_vs_finest_{order_name}.csv"), vs_fin, "Mesh")

    # ---------------------------------------------------------------
    # 3) Order-2 vs. order-3 comparison, at each mesh size: C12 and S.
    # ---------------------------------------------------------------
    order_csv = os.path.join(HERE, "order_comparison.csv")
    with open(order_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Mesh (um)", "C12 order2 (fF)", "C12 order3 (fF)",
                          "Delta C12 (fF)", "Delta C12 (%)"] +
                         [f"|dS_{p}| (linear)" for p in PARAMS] +
                         [f"|dS_{p}_dB|" for p in PARAMS])
        for mesh_label, key2, key3 in ORDER_PAIRS:
            if key2 not in data or key3 not in data:
                continue
            c2 = data[key2]["c12"] * 1e15
            c3 = data[key3]["c12"] * 1e15
            dc = c3 - c2
            dc_pct = 100.0 * dc / c2
            row = [mesh_label, fmt(c2), fmt(c3), fmt(dc), fmt(dc_pct, 3)]
            d_lin_vals, d_db_vals = [], []
            for pname in PARAMS:
                xa = data[key2]["s"][pname][0]
                xb = data[key3]["s"][pname][0]
                d_lin_vals.append(fmt(abs(xb - xa), 6))
                d_db_vals.append(fmt(abs(db(np.array([xb]))[0] - db(np.array([xa]))[0]), 4))
            writer.writerow(row + d_lin_vals + d_db_vals)
    print(f"Wrote order comparison table: {order_csv}")

    # ---------------------------------------------------------------
    # 4) Plot: C12 vs. mesh cell size, order 2 vs. order 3
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for series, color, marker, order_label in (
        (ORDER2_SERIES, "#4c72b0", "o", "order 2"),
        (ORDER3_SERIES, "#c44e52", "s", "order 3"),
    ):
        keys = [k for k, *_ in series if k in data]
        if not keys:
            continue
        xs = [data[k]["mesh_um"] for k in keys]
        ys = [data[k]["c12"] * 1e15 for k in keys]
        ax.plot(xs, ys, color=color, marker=marker, label=order_label)
    ax.set_xlabel("Uniform mesh cell size (um)")
    ax.set_ylabel("C12 (fF)")
    ax.set_title("C12 convergence vs. mesh cell size (1 GHz)")
    ax.invert_xaxis()
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "c12_convergence.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")

    # ---------------------------------------------------------------
    # 5) Plot: |S21| and |S11| vs. mesh cell size, order 2 vs. order 3
    #    (documentation aid, not a required mesh-quality metric)
    # ---------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, pname in zip(axes, ["S11", "S21"]):
        for series, color, marker, order_label in (
            (ORDER2_SERIES, "#4c72b0", "o", "order 2"),
            (ORDER3_SERIES, "#c44e52", "s", "order 3"),
        ):
            keys = [k for k, *_ in series if k in data]
            if not keys:
                continue
            xs = [data[k]["mesh_um"] for k in keys]
            ys = [db(np.array([data[k]["s"][pname][0]]))[0] for k in keys]
            ax.plot(xs, ys, color=color, marker=marker, label=order_label)
        ax.set_xlabel("Uniform mesh cell size (um)")
        ax.set_ylabel(f"|{pname}| (dB)")
        ax.set_title(f"{pname} vs. mesh (1 GHz)")
        ax.invert_xaxis()
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "s_param_convergence.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")

    # ---------------------------------------------------------------
    # 6) Sweep-only plot: C12 vs. frequency, 0-50 GHz, coarsest mesh
    #    (documentation only, not part of the mesh convergence metric)
    # ---------------------------------------------------------------
    sweep_key, sweep_label, sweep_fname = SWEEP_ENTRY
    nw_sweep = load(sweep_fname)
    if nw_sweep is not None:
        f_ghz = nw_sweep.frequency.f / 1e9
        c12_ff = c12_from_y(nw_sweep) * 1e15
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(f_ghz, c12_ff, color="#4c72b0")
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("C12 (fF)")
        ax.set_title(f"C12 vs. frequency ({sweep_label})")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, "c12_vs_frequency.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")

        # also drop the raw numbers as CSV for reference
        sweep_csv = os.path.join(HERE, "c12_vs_frequency.csv")
        with open(sweep_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Frequency (GHz)", "C12 (fF)"])
            for fg, cf in zip(f_ghz, c12_ff):
                writer.writerow([fmt(fg, 3), fmt(cf)])
        print(f"Wrote: {sweep_csv}")
    else:
        print(f"WARNING: missing {sweep_fname}, skipping frequency-sweep plot")


if __name__ == "__main__":
    main()
