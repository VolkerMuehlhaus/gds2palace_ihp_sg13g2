#!/usr/bin/env python
"""Order=1 vs order=2 comparison for the balun2x1 edge-coupled balun.

Reads palace.json (DOF, mesh elements, total solve time, peak RAM)
directly from each run's output directory -- same fields/paths as
gds2palace_ihp_sg13g2/scripts/palace_summary.py -- for the order=2
uniform mesh runs and the matching order=1 runs at the same cell sizes
(5/2/1 um), and produces a table + bar chart of solve time and DOF vs.
cell size, order 1 vs order 2. Also overlays Sdd11/Sdd21 magnitude to
show what accuracy is given up.
"""
import os
import csv
import json
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR = os.path.dirname(HERE)
PALACE_MODEL_DIR = os.path.join(STUDY_DIR, "palace_model")
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")

BASE = "balun2x1_edgecoupled_do200_w8_s2"
CELL_SIZES_UM = [5, 2, 1]
ORDER2_BASENAME = BASE + "_mesh{n}"
ORDER1_BASENAME = BASE + "_mesh{n}_order1"
ORDER2_SNP = "balun2x1_mesh{n}.s4p"
ORDER1_SNP = "balun2x1_mesh{n}_order1.s4p"


def read_palace_json(basename):
    path = os.path.join(PALACE_MODEL_DIR, f"{basename}_data", "output", basename, "palace.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    return {
        "duration_s": data.get("ElapsedTime", {}).get("Durations", {}).get("Total"),
        "peak_ram_mb": data.get("PeakMemoryMegabytes", {}).get("Total"),
        "dof": data.get("Problem", {}).get("DegreesOfFreedom"),
        "mesh_elements": data.get("Problem", {}).get("MeshElements"),
    }


def fmt_duration(s):
    if s is None:
        return "n/a"
    m, sec = divmod(int(round(s)), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {sec}s" if h else f"{m}m {sec}s"


Z01 = 200.0  # primary differential reference -- the balun's actual intended system impedance
Z02 = 50.0   # secondary differential reference -- the balun's actual intended system impedance


def sdd11_sdd21(nw):
    # real 200/50 ohm system-impedance reference (see analyze_convergence.py), not the naive
    # uniform 2x50=100 ohm value the raw port_Z0=50.0 ports would suggest
    Z = nw.z
    Zaa = Z[:, 0, 0] - Z[:, 0, 1] - Z[:, 1, 0] + Z[:, 1, 1]
    Zab = Z[:, 0, 2] - Z[:, 0, 3] - Z[:, 1, 2] + Z[:, 1, 3]
    Zba = Z[:, 2, 0] - Z[:, 2, 1] - Z[:, 3, 0] + Z[:, 3, 1]
    Zbb = Z[:, 2, 2] - Z[:, 2, 3] - Z[:, 3, 2] + Z[:, 3, 3]
    D = (Zaa + Z01) * (Zbb + Z02) - Zab * Zba
    Sdd11 = ((Zaa - Z01) * (Zbb + Z02) - Zab * Zba) / D
    Sdd21 = 2 * Zba * np.sqrt(Z01 * Z02) / D
    return Sdd11, Sdd21


def main():
    os.makedirs(PLOT_DIR, exist_ok=True)
    rows = []
    for n in CELL_SIZES_UM:
        o2 = read_palace_json(ORDER2_BASENAME.format(n=n))
        o1 = read_palace_json(ORDER1_BASENAME.format(n=n))
        rows.append((n, o1, o2))

    csv_path = os.path.join(HERE, "order_comparison_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Cell size (um)", "Order", "DOF", "Mesh elements", "Solve time", "Peak RAM (MB)"])
        for n, o1, o2 in rows:
            if o1:
                writer.writerow([n, 1, o1["dof"], o1["mesh_elements"], fmt_duration(o1["duration_s"]), o1["peak_ram_mb"]])
            if o2:
                writer.writerow([n, 2, o2["dof"], o2["mesh_elements"], fmt_duration(o2["duration_s"]), o2["peak_ram_mb"]])
    print(f"Wrote {csv_path}")
    for n, o1, o2 in rows:
        print(f"cellsize={n}um  order1: {o1}  order2: {o2}")

    have_data = any(o1 and o2 for _, o1, o2 in rows)
    if not have_data:
        print("No completed runs found yet for order comparison plot.")
        return

    # ---- bar chart: solve time and DOF, order1 vs order2 ----
    fig, (ax_t, ax_d) = plt.subplots(1, 2, figsize=(11, 4.5))
    x = np.arange(len(CELL_SIZES_UM))
    width = 0.35
    t1 = [o1["duration_s"] if o1 else 0 for _, o1, _ in rows]
    t2 = [o2["duration_s"] if o2 else 0 for _, _, o2 in rows]
    d1 = [o1["dof"] if o1 else 0 for _, o1, _ in rows]
    d2 = [o2["dof"] if o2 else 0 for _, _, o2 in rows]

    ax_t.bar(x - width / 2, t1, width, label="order 1")
    ax_t.bar(x + width / 2, t2, width, label="order 2")
    ax_t.set_xticks(x)
    ax_t.set_xticklabels([f"{n} um" for n in CELL_SIZES_UM])
    ax_t.set_ylabel("Solve time (s)")
    ax_t.set_title("Solve time: order 1 vs order 2")
    ax_t.legend()
    ax_t.grid(True, alpha=0.3, axis='y')

    ax_d.bar(x - width / 2, d1, width, label="order 1")
    ax_d.bar(x + width / 2, d2, width, label="order 2")
    ax_d.set_xticks(x)
    ax_d.set_xticklabels([f"{n} um" for n in CELL_SIZES_UM])
    ax_d.set_ylabel("Degrees of freedom")
    ax_d.set_title("DOF: order 1 vs order 2")
    ax_d.legend()
    ax_d.grid(True, alpha=0.3, axis='y')

    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "order_comparison_time_dof.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path}")

    # ---- Sdd accuracy overlay: order1 vs order2 at each cell size ----
    fig, (ax_11, ax_21) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    colors = ["#4c72b0", "#dd8452", "#55a868"]
    for idx, n in enumerate(CELL_SIZES_UM):
        color = colors[idx % len(colors)]
        for order, snp_pattern, style in [(1, ORDER1_SNP, "--"), (2, ORDER2_SNP, "-")]:
            path = os.path.join(SNP_DIR, snp_pattern.format(n=n))
            if not os.path.isfile(path):
                continue
            nw = rf.Network(path)
            sdd11, sdd21 = sdd11_sdd21(nw)
            freq_ghz = nw.frequency.f / 1e9
            ax_11.plot(freq_ghz, 20 * np.log10(np.abs(sdd11)), color=color, linestyle=style,
                       label=f"{n} um, order {order}")
            ax_21.plot(freq_ghz, 20 * np.log10(np.abs(sdd21)), color=color, linestyle=style,
                       label=f"{n} um, order {order}")
    ax_11.set_ylabel("|Sdd11| (dB)")
    ax_11.grid(True, alpha=0.3)
    ax_11.legend(fontsize=7)
    ax_11.set_title(f"Order 1 (dashed) vs order 2 (solid): Sdd11, Sdd21 (Z01={Z01:.0f} ohm primary, Z02={Z02:.0f} ohm secondary)")
    ax_21.set_xlabel("Frequency (GHz)")
    ax_21.set_ylabel("|Sdd21| (dB)")
    ax_21.grid(True, alpha=0.3)
    fig.tight_layout()
    out_path2 = os.path.join(PLOT_DIR, "order_comparison_sdd.png")
    fig.savefig(out_path2, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path2}")


if __name__ == "__main__":
    main()
