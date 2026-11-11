"""Bar chart of the run time per model: this study (v4) against the v3 study.

Reads results/run_data.csv (this study) and results/run_data_v3.csv (the v3 runs), both written by
study_tables.py, and writes plots/speedup.png. Shows the 8 models of the summary table; the title gives
the sum over all runs of the study.

usage: python plot_speedup.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))

# one hue, two shades: before (light) and after (dark)
C_OLD, C_NEW = "#86b6ef", "#184f95"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SUMMARY = ["surfacemesh_2um_viamerge", "surfacemesh_2um_noviamerge", "surfacemesh_2um_mergecorrection",
           "2um_mergecorrection_filled", "2um_passicut", "5um_passi3D", "2um_passi3D", "1um_passi3D"]
LABEL_OLD = "v3 study: gds2palace 0.8.2"
LABEL_NEW = "this study: gds2palace 0.10.2"


def read(name):
    with open(os.path.join(here, name), encoding="utf-8") as f:
        return {r["model"]: r for r in csv.DictReader(f)}


def mmss(seconds):
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def hm(seconds):
    return f"{int(seconds // 3600)} h {int(round(seconds % 3600 / 60))} min"


old, new = read("run_data_v3.csv"), read("run_data.csv")
common = [m for m in old if m in new]
sum_old = sum(float(old[m]["time_s"]) for m in common)
sum_new = sum(float(new[m]["time_s"]) for m in common)

models = [m for m in SUMMARY if m in common]
fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
h = 0.36
xmax = max(float(old[m]["time_s"]) for m in models) / 60
for i, m in enumerate(models):
    y = len(models) - 1 - i
    t_old, t_new = float(old[m]["time_s"]), float(new[m]["time_s"])
    ax.barh(y + h / 2 + 0.02, t_old / 60, height=h, color=C_OLD, label=LABEL_OLD if i == 0 else None)
    ax.barh(y - h / 2 - 0.02, t_new / 60, height=h, color=C_NEW, label=LABEL_NEW if i == 0 else None)
    ax.text(t_old / 60 + 0.012 * xmax, y + h / 2 + 0.02, mmss(t_old), va="center", ha="left", fontsize=9, color=INK2)
    ax.text(t_new / 60 + 0.012 * xmax, y - h / 2 - 0.02, f"{mmss(t_new)}   {t_old / t_new:.1f}x faster",
            va="center", ha="left", fontsize=9, color=INK, fontweight="bold")
ax.set_yticks(range(len(models)))
ax.set_yticklabels([new[m]["label"] for m in reversed(models)], fontsize=10, color=INK)
ax.set_xlim(0, xmax * 1.16)
ax.set_xlabel("Run time of the frequency sweep (minutes), 16 cores", fontsize=10, color=INK2)
ax.xaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.tick_params(axis="both", length=0, colors=INK2)
for side in ("top", "right", "left", "bottom"):
    ax.spines[side].set_visible(False)
ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.97), frameon=False, fontsize=10, labelcolor=INK)
fig.suptitle(f"All {len(common)} models of the study: {hm(sum_old)} before, {hm(sum_new)} now "
             f"({sum_old / sum_new:.1f}x faster)", fontsize=13, color=INK, fontweight="bold", x=0.02, ha="left")
ax.set_title("Same model scripts, same machine, same Palace version (0.18). L, Q and SRF agree within 0.1 %.", fontsize=10, color=INK2, loc="left")
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(here, "plots", "speedup.png")
fig.savefig(out, dpi=125, facecolor=SURFACE)
print("wrote", out)
print(f"sum of {len(common)} runs: {hm(sum_old)} -> {hm(sum_new)}, {sum_old / sum_new:.2f}x")
for m in common:
    print(f"  {m:32s} {mmss(float(old[m]['time_s'])):>8s} -> {mmss(float(new[m]['time_s'])):>8s}  "
          f"{float(old[m]['time_s']) / float(new[m]['time_s']):.2f}x")
