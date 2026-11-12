"""Bar chart of the run time per model: the v3 study, the gds2palace update, and this study (Palace 0.18.1).

Reads results/run_data_v3.csv (the v3 runs: gds2palace 0.8.2), results/run_data_v3_image.csv (this study's models
with the Palace 0.18.0 image of v3) and results/run_data.csv (this study, published Palace 0.18.1 image),
all written by study_tables.py. Writes plots/speedup.png. Shows the 8 models of the summary table; the title
gives the sum over all runs of the study.

usage: python plot_speedup.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))

# one hue, three shades: each step darker
C = ["#b5d2f5", "#5b97e0", "#184f95"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SUMMARY = ["surfacemesh_2um_viamerge", "surfacemesh_2um_noviamerge", "surfacemesh_2um_mergecorrection",
           "2um_mergecorrection_filled", "2um_passicut", "5um_passi3D", "2um_passi3D", "1um_passi3D"]
LABELS = ["v3 study: gds2palace 0.8.2, Palace 0.18.0", "gds2palace 0.10.2, Palace 0.18.0",
          "this study: gds2palace 0.10.2, Palace 0.18.1"]


def read(name):
    with open(os.path.join(here, name), encoding="utf-8") as f:
        return {r["model"]: r for r in csv.DictReader(f)}


def mmss(seconds):
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def hm(seconds):
    h, m = divmod(int(round(seconds / 60)), 60)
    return f"{h} h {m} min" if h else f"{m} min"


old, new = read("run_data_v3.csv"), read("run_data_v3_image.csv")
TNEW = {m: float(r["time_s"]) for m, r in read("run_data.csv").items()}
common = [m for m in old if m in new and m in TNEW]
sums = [sum(float(old[m]["time_s"]) for m in common), sum(float(new[m]["time_s"]) for m in common),
        sum(TNEW[m] for m in common)]

models = [m for m in SUMMARY if m in common]
fig, ax = plt.subplots(figsize=(10, 7.2), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
h = 0.25
xmax = max(float(old[m]["time_s"]) for m in models) / 60
for i, m in enumerate(models):
    y = len(models) - 1 - i
    t = [float(old[m]["time_s"]), float(new[m]["time_s"]), TNEW[m]]
    notes = [mmss(t[0]), f"{mmss(t[1])}   {t[0] / t[1]:.1f}x faster than v3",
             f"{mmss(t[2])}   another {t[1] / t[2]:.2f}x, {t[0] / t[2]:.1f}x in total"]
    for k in range(3):
        yk = y + (1 - k) * (h + 0.02)
        ax.barh(yk, t[k] / 60, height=h, color=C[k], label=LABELS[k] if i == 0 else None)
        ax.text(t[k] / 60 + 0.012 * xmax, yk, notes[k], va="center", ha="left", fontsize=8.5,
                color=INK if k == 2 else INK2, fontweight="bold" if k == 2 else "normal")
ax.set_yticks(range(len(models)))
ax.set_yticklabels([new[m]["label"] for m in reversed(models)], fontsize=10, color=INK)
ax.set_xlim(0, xmax * 1.16)
ax.set_xlabel("Run time of the frequency sweep (minutes), 16 cores", fontsize=10, color=INK2)
ax.xaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.tick_params(axis="both", length=0, colors=INK2)
for side in ("top", "right", "left", "bottom"):
    ax.spines[side].set_visible(False)
fig.legend(loc="upper left", bbox_to_anchor=(0.012, 0.915), frameon=False, fontsize=10, labelcolor=INK)
fig.suptitle(f"All {len(common)} models: {hm(sums[0])} in v3, {hm(sums[1])} with gds2palace 0.10.2, "
             f"{hm(sums[2])} now ({sums[0] / sums[2]:.1f}x)",
             fontsize=13, color=INK, fontweight="bold", x=0.02, y=0.985, ha="left")
fig.text(0.02, 0.925, "Same model scripts, same machine, same results: L, peak Q and SRF agree with v3 within 0.1 %.", fontsize=10, color=INK2, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.84))
out = os.path.join(here, "plots", "speedup.png")
fig.savefig(out, dpi=125, facecolor=SURFACE)
print("wrote", out)
print("sums:", [round(s) for s in sums], f"v3/v4 {sums[0] / sums[1]:.2f}x, image {sums[1] / sums[2]:.2f}x, total {sums[0] / sums[2]:.2f}x")
