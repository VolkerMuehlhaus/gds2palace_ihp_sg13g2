# Joins the two split models into the 4-port of the whole assembly, makes a 2-port with one 50 ohm GSG port at
# each end of the line from it, and compares that with assembly.py if that result exists.
#
#   python join_split.py
#
# split_upper: ports 1-4 = probe ports, 5 = tube port on the left signal pillar, 6 = on the right one
# split_lower: ports 1, 2 = tube ports on the same pillars
# Writes results/split_joined.s4p and results/split_joined_gsg.s2p, and with the reference
# results/assembly_gsg.s2p and results/split_vs_assembly.png.

import glob
import os

import numpy as np
import skrf as rf

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def result(model, nports):
    """the Touchstone file that combine_snp wrote for a model (not the _deembedded or _dc ones);
    without a run of your own, the result shipped in results/"""
    files = glob.glob(f"palace_model/{model}_data/output/{model}/{model}.s{nports}p")
    files += glob.glob(f"results/{model}.s{nports}p")
    if not files:
        return None
    print("reading", files[0])
    return rf.Network(files[0])


upper, lower = result("split_upper", 6), result("split_lower", 2)
if upper is None or lower is None:
    raise SystemExit("run split_lower and split_upper first (see README.md)")
assert np.allclose(upper.f, lower.f), "the two split models must use the same frequencies"

# connect upper port 5 (index 4) to lower port 1 (index 0): ports are now upper 1-4, upper 6, lower 2
joined = rf.network.connect(upper, 4, lower, 0)
# connect upper port 6 with lower port 2, both in the same network now
joined = rf.network.innerconnect(joined, 4, 5)
joined.name = "split_joined"
os.makedirs("results", exist_ok=True)
joined.write_touchstone(os.path.join("results", "split_joined"))
print("written results/split_joined.s4p")


def gsg(network):
    """2-port with one 50 ohm GSG port at each end of the line: ports 1+2 and 3+4 in parallel.
    The two gap ports of a pair both point from the signal pad to a ground pad, so the GSG excitation is their
    common mode: renormalize each gap port to 100 ohm, then take the common mode of each pair (reference 50 ohm).
    This is what one Palace port with the two gaps as elements would give."""
    n = network.copy()
    n.renormalize(100)
    a = np.zeros((2, 4))
    a[0, :2] = a[1, 2:] = 1 / np.sqrt(2)
    return rf.Network(frequency=n.frequency, s=a @ n.s @ a.T, z0=50, name=network.name + "_gsg")


joined_gsg = gsg(joined)
joined_gsg.write_touchstone(os.path.join("results", "split_joined_gsg"))
print("written results/split_joined_gsg.s2p")

reference = result("assembly", 4)
if reference is None:
    raise SystemExit("no result of assembly.py: nothing to compare with")
assert np.allclose(reference.f, joined.f), "split and assembly models must use the same frequencies"
reference_gsg = gsg(reference)
reference_gsg.write_touchstone(os.path.join("results", "assembly_gsg"))
print("written results/assembly_gsg.s2p")

joined, reference = joined_gsg, reference_gsg
f = joined.f / 1e9
diff = np.abs(joined.s - reference.s)
print("largest |S(split, joined) - S(assembly)| of the 4 GSG S-parameters:")
for fmax in (10, 30, 60, 100):
    print(f"  up to {fmax:3d} GHz: {diff[f <= fmax].max():.4f}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def smith_zoomed(ax, s_ref, s_joined, color):
    """S11 in the reflection plane, zoomed to the center of the Smith chart (50 ohm), with its own grid of
    constant resistance and reactance circles; markers every 20 GHz"""
    lim = 0.1
    t = np.linspace(0, 2 * np.pi, 721)
    for r in (0.8, 0.9, 1.0, 1.1, 1.2):          # constant r: center r/(1+r), radius 1/(1+r)
        ax.plot(r / (1 + r) + np.cos(t) / (1 + r), np.sin(t) / (1 + r), color="0.8", lw=0.6)
        ax.annotate(f"r={r:g}", ((r - 1) / (r + 1), 0), xytext=(2, 2), textcoords="offset points", fontsize=7,
                    color="0.5")
    for x in (-0.2, -0.1, 0.1, 0.2):                         # constant x: center (1, 1/x), radius 1/|x|
        ax.plot(1 + np.cos(t) / abs(x), 1 / x + np.sin(t) / abs(x), color="0.8", lw=0.6)
        g = 1j * x / (2 + 1j * x)                            # where the circle crosses r = 1
        ax.annotate(f"x={x:g}", (g.real, g.imag), xytext=(2, 2), textcoords="offset points", fontsize=7,
                    color="0.5")
    ax.axhline(0, color="0.8", lw=0.6)
    for m in (0.05, 0.1):                                    # constant |S11|
        ax.plot(m * np.cos(t), m * np.sin(t), ":", color="0.6", lw=0.6)
    ax.plot(s_ref.real, s_ref.imag, color=color, label="assembly")
    ax.plot(s_joined.real, s_joined.imag, "--", color="k", label="split, joined")
    ax.legend(fontsize=8, loc="upper right")
    marks = [k for k, fk in enumerate(f) if fk % 20 == 0 and fk > 0]
    ax.plot(s_ref.real[marks], s_ref.imag[marks], "o", color=color, ms=4)
    ax.plot(s_joined.real[marks], s_joined.imag[marks], "o", mfc="none", color="k", ms=4)
    center = s_ref[marks].mean()
    for k in marks:
        away = s_ref[k] - center                             # put the label on the side away from the curve
        away = away / abs(away) if abs(away) > 0 else 1
        ax.annotate(f"{f[k]:g} GHz", (s_ref.real[k], s_ref.imag[k]), xytext=(16 * away.real, 16 * away.imag),
                    textcoords="offset points", fontsize=7, color=color, ha="center", va="center")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Re S11")
    ax.set_ylabel("Im S11")
    ax.set_title(f"S11, Smith chart zoomed to |S11| < {lim:g}", fontsize=9)


# one row per S-parameter: S11 and S21 have very different magnitudes
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for row, ((i, j), color) in enumerate((((0, 0), "C0"), ((1, 0), "C1"))):
    label = f"S{i + 1}{j + 1}"
    ax_db, ax_phase, ax_diff = axes[row]
    ax_db.plot(f, 20 * np.log10(np.abs(reference.s[:, i, j])), color=color, label="assembly")
    ax_db.plot(f, 20 * np.log10(np.abs(joined.s[:, i, j])), "--", color="k", label="split, joined")
    if label == "S11":
        smith_zoomed(ax_phase, reference.s[:, i, j], joined.s[:, i, j], color)
    else:
        ax_phase.plot(f, np.degrees(np.angle(reference.s[:, i, j])), color=color, label="assembly")
        ax_phase.plot(f, np.degrees(np.angle(joined.s[:, i, j])), "--", color="k", label="split, joined")
    ax_diff.plot(f, diff[:, i, j], color=color)
    ax_db.set_ylabel(f"|{label}| (dB)")
    if label != "S11":
        ax_phase.set_ylabel(f"phase of {label} (degree)")
        ax_phase.set_ylim(-180, 180)
        ax_phase.set_yticks(range(-180, 181, 90))
    ax_diff.set_ylabel(f"|{label}(split, joined) - {label}(assembly)|")
    ax_diff.set_ylim(bottom=0)
    ax_db.legend(fontsize=8)
    if label != "S11":
        ax_phase.legend(fontsize=8)
for ax in axes.flat:
    if ax is not axes[0, 1]:
        ax.set_xlabel("frequency (GHz)")
        ax.grid(True, alpha=0.4)
fig.tight_layout()
fig.savefig(os.path.join("results", "split_vs_assembly.png"), dpi=110)
print("written results/split_vs_assembly.png")
