#!/usr/bin/env python
"""Plots and numbers for README.md (conformal / single-frequency AMR on the D-band balun).

Reads results/snp/ and results/runs.csv (written by collect_results.py), and two runs of the parent study in
../../results/snp/ for comparison, and writes to results/plots/:

  story_passes_150GHz.png    - stage 1: insertion loss and |S11| at 150 GHz after every AMR pass, over unknowns
  story_stage2_band.png      - stage 2: full sweep on the saved 150 GHz meshes vs. the reference
  story_accuracy_vs_cost.png - Max|dS| vs. the reference, over total solve time, for all ways to get there

The reference is the full-band nonconformal AMR run of this study (amrnc_full, 5 passes, 4.6M unknowns): the same
settings as the parent study's AMR run, rerun on the same Palace version as all other runs here.

It also prints the numbers quoted in README.md.

Balun figures of merit as in the parent study (port 1 = input, ports 2/3 = balanced outputs):
  insertion loss  IL = -10*log10(|S21|^2 + |S31|^2)
  amplitude imb.  20*log10(|S21| / |S31|)
  phase imbalance 180 deg - |angle(S21 / S31)|
"""
import csv
import os

import matplotlib
import numpy as np
import skrf as rf

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP = os.path.join(HERE, "snp")
PARENT_SNP = os.path.join(HERE, "..", "..", "results", "snp")
PLOT_DIR = os.path.join(HERE, "plots")

F_AMR = 150e9
BAND = (140e9, 170e9)

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
GRAY = "#8a8984"
ORANGE = "#eb6834"
AQUA = "#1baf7a"

REF = "amrnc_full"                       # full-band nonconformal AMR, 5 passes (this study)
REF_LABEL = "full-band AMR, 5 passes"
PARENT = {"mesh5_ref": "balun_mesh5um.s3p", "mesh1_ref": "balun_mesh1um.s3p", REF: "balun_amr5_final.s3p"}

# stage 1 runs: label, run name, color, marker, line style
STAGE1 = [
    ("conformal, UpdateFraction 0.3", "amrc_f150_uf03", "#0d366b", "o", "-"),
    ("conformal, UpdateFraction 0.5", "amrc_f150_uf05", "#2a78d6", "s", "-"),
    ("conformal, UpdateFraction 0.7", "amrc_f150_uf07", "#86b6ef", "^", "-"),
    ("nonconformal, UpdateFraction 0.7", "amrnc_f150_uf07", ORANGE, "D", "--"),
]
# stage 2: full sweep on a saved stage-1 mesh; label, stage-1 run that made the mesh, color
STAGE2 = [
    ("1.28M", "amrc_f150_uf05_p3", "#86b6ef"),
    ("2.02M", "amrc_f150_uf07", "#2a78d6"),
    ("3.42M", "amrc_f150_uf03", "#0d366b"),
]
# single stage: AMR over the full 100-200 GHz sweep in every pass; label, run, color, marker, line style
SINGLE_STAGE = [
    ("1 stage, conformal, UF 0.7 (large steps)", "amrc_uf07_full", "#0d366b", "^", "-."),
    ("1 stage, conformal, UF 0.3, MaxSize 1.2M", "amrc_uf03_full", AQUA, "o", "-"),
    ("1 stage, nonconformal, UF 0.7 (default)", REF, ORANGE, "D", "--"),
]


def load(path):
    return rf.Network(path)


def snp(name):
    return os.path.join(SNP, name + ".s3p")


def merits(s):
    """figures of merit for an S-matrix array (..., 3, 3)"""
    s11, s21, s31 = s[..., 0, 0], s[..., 1, 0], s[..., 2, 0]
    return {
        "IL": -10 * np.log10(np.abs(s21) ** 2 + np.abs(s31) ** 2),
        "S11": 20 * np.log10(np.abs(s11)),
        "amp": 20 * np.log10(np.abs(s21) / np.abs(s31)),
        "phase": 180 - np.abs(np.angle(s21 / s31, deg=True)),
    }


def at(ntw, f=F_AMR):
    return ntw.s[np.argmin(np.abs(ntw.f - f))]


def runs():
    with open(os.path.join(HERE, "runs.csv")) as f:
        return {r["name"]: r for r in csv.DictReader(f)}


def passes(run, table):
    return sorted((r for r in table.values() if r["run"] == run), key=lambda r: int(r["pass"]))


def minutes(table, *names):
    """total solve time; Palace's time of an AMR run is cumulative, so the last pass covers the whole run"""
    return sum(float(table[n]["time_s"]) for n in names) / 60


def peak_ram(table, *runs_):
    return max(float(r["peak_ram_GB"]) for run in runs_ for r in passes(run, table))


def style(ax, band=True):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    if band:
        ax.axvspan(BAND[0] / 1e9, BAND[1] / 1e9, color="#f1efe8", zorder=0)


def log_axis(axis, ticks):
    axis.set_ticks(ticks)
    axis.set_ticklabels([f"{t:g}" for t in ticks])
    axis.set_minor_formatter(matplotlib.ticker.NullFormatter())


def save(fig, name):
    out = os.path.join(PLOT_DIR, name)
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_passes(table):
    panels = [("IL", "Insertion loss at 150 GHz (dB)"), ("S11", "Input match |S11| at 150 GHz (dB)")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    for label, run, color, marker, ls in STAGE1:
        rows = passes(run, table)
        x = [int(r["unknowns"]) / 1e6 for r in rows]
        m = merits(np.array([load(snp(r["name"])).s[0] for r in rows]))
        for ax, (key, _) in zip(axes, panels):
            ax.plot(x, m[key], color=color, marker=marker, markersize=8, linewidth=2, linestyle=ls, label=label,
                    zorder=3)
    for ax, (key, title) in zip(axes, panels):
        style(ax, band=False)
        ax.set_xscale("log")
        log_axis(ax.xaxis, [0.2, 0.5, 1, 2, 5])
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Unknowns (millions, log scale)", color=INK2)
        # reference lines, labeled on the left where the curves are still far above them
        for rlabel, name, rls in (("1 µm uniform", "mesh1_ref", ":"), (REF_LABEL + " (reference)", REF, "--")):
            v = merits(at(load(snp(name))))[key]
            ax.axhline(v, color=GRAY, linewidth=1.2, linestyle=rls, zorder=2)
            ax.annotate(rlabel, (0.02, v), xycoords=("axes fraction", "data"), xytext=(0, 3),
                        textcoords="offset points", ha="left", fontsize=8, color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=9,
               title="AMR at 150 GHz only, from the 5 µm mesh (one marker per pass)", title_fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.83))
    save(fig, "story_passes_150GHz.png")


def plot_stage2():
    series = [("1 µm uniform", snp("mesh1_ref"), GRAY, ":")]
    series += [(f"150 GHz mesh, {label} unknowns", snp(run + "_s2"), color, "-") for label, run, color in STAGE2]
    series += [(REF_LABEL + " (reference)", snp(REF), ORANGE, "--")]
    panels = [("IL", "Insertion loss (dB)"), ("S11", "Input match |S11| (dB)")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0), sharex=True)
    for label, path, color, ls in series:
        ntw = load(path)
        m = merits(ntw.s)
        for ax, (key, _) in zip(axes, panels):
            ax.plot(ntw.f / 1e9, m[key], color=color, linewidth=2, linestyle=ls, label=label)
    for ax, (_, title) in zip(axes, panels):
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Frequency (GHz)", color=INK2)
        ax.axvline(F_AMR / 1e9, color=INK2, linewidth=0.8)
    axes[0].text(F_AMR / 1e9, 0.97, " AMR frequency", transform=axes[0].get_xaxis_transform(), fontsize=8,
                 color=INK2, va="top")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    save(fig, "story_stage2_band.png")


def plot_accuracy_vs_cost(table):
    ref = load(snp(REF))
    fig, ax = plt.subplots(figsize=(8.5, 5))
    style(ax, band=False)

    for label, name, dxy in (("5 µm uniform", "mesh5_ref", (8, 4)), ("1 µm uniform", "mesh1_ref", (6, -14))):
        t, d = minutes(table, name), np.abs(load(snp(name)).s - ref.s).max()
        ax.plot([t], [d], marker="o", color=GRAY, markersize=9, linestyle="none", zorder=3)
        ax.annotate(label, (t, d), textcoords="offset points", xytext=dxy, fontsize=9, color=INK)

    # single stage: one marker per AMR pass, at the cumulative time; the last pass of the reference run is the
    # reference itself (Max|dS| = 0), shown as a vertical line instead
    for label, run, color, marker, ls in SINGLE_STAGE:
        rows = [r for r in passes(run, table) if not (run == REF and r["final"] == "True")]
        t = [float(r["time_s"]) / 60 for r in rows]
        d = [np.abs(load(snp(r["name"])).s - ref.s).max() for r in rows]
        ax.plot(t, d, color=color, marker=marker, markersize=8, linewidth=2, linestyle=ls, label=label, zorder=3)
    t_ref = minutes(table, REF)
    ax.axvline(t_ref, color=ORANGE, linewidth=1.2, linestyle=":")
    ax.text(t_ref, 0.0045, f"reference = its 5th pass:\n{t_ref:.0f} min, {peak_ram(table, REF):.0f} GB ", fontsize=8,
            color=INK2, ha="right", va="center")

    for i, (label, run, color) in enumerate(STAGE2):
        t, d = minutes(table, run, run + "_s2"), np.abs(load(snp(run + "_s2")).s - ref.s).max()
        ax.plot([t], [d], marker="s", color=color, markersize=9, linestyle="none", zorder=4,
                label="2 stages: AMR at 150 GHz + sweep on that mesh" if i == 0 else None)
        ax.annotate(label, (t, d), textcoords="offset points", xytext=(8, 4 if label == "3.42M" else -12),
                    fontsize=9, color=INK)

    ax.set_xscale("log")
    ax.set_yscale("log")
    log_axis(ax.xaxis, [0.5, 1, 2, 5, 10, 20, 50, 100])
    log_axis(ax.yaxis, [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1])
    ax.set_xlim(0.4, 130)
    ax.set_ylim(0.0009, 0.2)
    ax.set_xlabel("Total solve time (min, log scale; AMR = all passes so far, 2 stages = both)", color=INK2)
    ax.set_ylabel("Max |ΔS| vs. reference (log scale)", color=INK2)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    save(fig, "story_accuracy_vs_cost.png")


def print_numbers(table):
    ref = load(snp(REF))
    print("\nReproduction check (this study vs. the parent study on Palace 0.17), Max|dS| over the band:")
    for name, old in PARENT.items():
        print(f"  {name}: {np.abs(load(snp(name)).s - load(os.path.join(PARENT_SNP, old)).s).max():.4f}")

    print("\nStage 1, every pass at 150 GHz:")
    print(f"{'pass':26s} {'unknowns':>10s} {'time':>7s} {'RAM GB':>7s} {'err':>7s} {'IL':>6s} {'S11':>7s} "
          f"{'dS 1um':>7s} {'dS ref':>7s}")
    for run in [r for _, r, *_ in STAGE1] + ["amrc_f150_uf05_p3"]:
        for r in passes(run, table):
            s = load(snp(r["name"])).s[0]
            m = merits(s)
            print(f"{r['name']:26s} {int(r['unknowns']):>10,} {float(r['time_s']):>6.0f}s "
                  f"{float(r['peak_ram_GB']):>7.1f} {float(r['error_norm']):>7.4f} {m['IL']:6.3f} {m['S11']:7.2f} "
                  f"{np.abs(s - at(load(snp('mesh1_ref')))).max():7.4f} {np.abs(s - at(ref)).max():7.4f}")
    m = merits(at(ref))
    print(f"  reference at 150 GHz: IL {m['IL']:.3f} dB, S11 {m['S11']:.2f} dB")

    print("\nStage 2 consistency (sweep on the saved mesh vs. last stage-1 pass, at 150 GHz):")
    for _, run, _ in STAGE2:
        d = np.abs(at(load(snp(run + "_s2"))) - load(snp(run)).s[0]).max()
        print(f"  {run}: unknowns {table[run]['unknowns']} / {table[run + '_s2']['unknowns']}, Max|dS| {d:.5f}")

    print("\nFull band: in-band figures of merit and cost")
    print(f"{'variant':34s} {'unknowns':>10s} {'min':>6s} {'RAM':>5s} {'IL in band':>12s} {'null':>5s} "
          f"{'dS ref':>7s}")
    variants = [("5 µm uniform", ["mesh5_ref"], "mesh5_ref"), ("1 µm uniform", ["mesh1_ref"], "mesh1_ref")]
    variants += [(f"2 stages, {l}", [r, r + "_s2"], r + "_s2") for l, r, _ in STAGE2]
    for label, run, *_ in SINGLE_STAGE:
        variants += [(f"{run} pass {r['pass']}", [r["name"]], r["name"]) for r in passes(run, table)]
    for label, names, result in variants:
        ntw = load(snp(result))
        band = (ntw.f >= BAND[0]) & (ntw.f <= BAND[1])
        m = merits(ntw.s)
        null = ntw.f[np.argmin(np.abs(ntw.s[:, 0, 0]))] / 1e9
        ram = max(float(table[n]["peak_ram_GB"]) for n in names)
        print(f"{label:34s} {int(table[result]['unknowns']):>10,} {minutes(table, *names):6.1f} {ram:5.1f} "
              f"{m['IL'][band].min():5.3f}..{m['IL'][band].max():5.3f} {null:5.0f} {np.abs(ntw.s - ref.s).max():7.4f}")


if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)
    table = runs()
    plot_passes(table)
    plot_stage2()
    plot_accuracy_vs_cost(table)
    print_numbers(table)
