#!/usr/bin/env python
"""Quick & dirty order=1 vs order=2 comparison for the ind_frame inductor.

Reads palace.json (DOF, mesh elements, total solve time, peak RAM) directly
from each run's output directory -- same fields/paths as
gds2palace_ihp_sg13g2/scripts/palace_summary.py -- for the order=2 uniform
mesh runs and the matching order=1 runs at the same cell sizes (1/2/3 um),
and produces a table + bar chart of solve time and DOF vs. cell size, order 1
vs order 2. Also overlays S11/S21 magnitude to show what accuracy is given
up (see plot_inductor_convergence.py for the L/Q view of the same trade-off).

This is intentionally not a full convergence study: order=1 is only checked
at 3 cell sizes as a quick timing/accuracy sanity check, not carried through
AMR or the full 1-5 um sweep.
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

CELL_SIZES_UM = [3, 2, 1]
ORDER2_BASENAME = "palace_ind_frame_mesh{n}"
ORDER1_BASENAME = "palace_ind_frame_mesh{n}_order1"
ORDER2_SNP = "ind_frame_mesh{n}.s2p"
ORDER1_SNP = "ind_frame_mesh{n}_order1.s2p"


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

    # ---- S-parameter accuracy overlay: order1 vs order2 at each cell size ----
    fig, (ax_s11, ax_s21) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    colors = ["#4c72b0", "#dd8452", "#55a868"]
    for idx, n in enumerate(CELL_SIZES_UM):
        color = colors[idx % len(colors)]
        for order, snp_pattern, style in [(1, ORDER1_SNP, "--"), (2, ORDER2_SNP, "-")]:
            path = os.path.join(SNP_DIR, snp_pattern.format(n=n))
            if not os.path.isfile(path):
                continue
            nw = rf.Network(path)
            freq_ghz = nw.frequency.f / 1e9
            ax_s11.plot(freq_ghz, 20 * np.log10(np.abs(nw.s[:, 0, 0])), color=color, linestyle=style,
                        label=f"{n} um, order {order}")
            ax_s21.plot(freq_ghz, 20 * np.log10(np.abs(nw.s[:, 1, 0])), color=color, linestyle=style,
                        label=f"{n} um, order {order}")
    ax_s11.set_ylabel("|S11| (dB)")
    ax_s11.grid(True, alpha=0.3)
    ax_s11.legend(fontsize=7)
    ax_s11.set_title("Order 1 (dashed) vs order 2 (solid): S11, S21")
    ax_s21.set_xlabel("Frequency (GHz)")
    ax_s21.set_ylabel("|S21| (dB)")
    ax_s21.grid(True, alpha=0.3)
    fig.tight_layout()
    out_path2 = os.path.join(PLOT_DIR, "order_comparison_s_params.png")
    fig.savefig(out_path2, dpi=150)
    plt.close(fig)
    print(f"Wrote plot: {out_path2}")


if __name__ == "__main__":
    main()
