#!/usr/bin/env python
"""Compare the L6n2 study runs with ComplexCoarseSolve (this folder) against the original
runs without it (../more_accurate_models_L6n2), model by model: DOF, GMRES iterations,
solve time, peak RAM and the largest S-parameter difference.

Both sets use the same meshes and configs, apart from the one setting, and the same Palace
build on hpz2 (16 MPI ranks), so the differences come from the setting alone.

Run from anywhere in the d:\\venv\\palace venv; reads palace_model/<name>_data/output/*/
palace.json and port-S.csv of both folders, and palace.log of this folder.
"""
import os
import re
import glob
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# normpath: with the "..\.." left in, the longer model paths exceed Windows' 260-character
# limit and glob silently finds nothing
NEW = os.path.normpath(os.path.join(HERE, "..", "palace_model"))
OLD = os.path.normpath(os.path.join(HERE, "..", "..", "more_accurate_models_L6n2", "palace_model"))


def read_port_s(path):
    """Complex S-parameters from Palace's port-S.csv, as {(i, j): array}, sorted by frequency."""
    rows = [l.split(",") for l in open(path) if l.strip()]
    head = [c.strip() for c in rows[0]]
    data = np.array([[float(x) for x in r] for r in rows[1:]])
    data = data[np.argsort(data[:, 0])]
    s = {}
    for col, h in enumerate(head):
        m = re.match(r"\|S\[(\d+)\]\[(\d+)\]\| \(dB\)", h)
        if m:
            ang = head.index(f"arg(S[{m.group(1)}][{m.group(2)}]) (deg.)")
            s[(int(m.group(1)), int(m.group(2)))] = 10 ** (data[:, col] / 20) * np.exp(1j * np.radians(data[:, ang]))
    return data[:, 0], s


def run(data_dir):
    js = glob.glob(os.path.join(data_dir, "output", "*", "palace.json"))
    if not js:
        return None
    j = json.load(open(js[0]))
    lin = j["LinearSolver"]
    log = os.path.join(data_dir, "palace.log")
    per_solve = nonconv = None
    if os.path.isfile(log):
        text = open(log, errors="replace").read()
        its = [int(x) for x in re.findall(r"solver (?:did NOT )?converged? in (\d+) iteration", text)]
        per_solve = max(its) if its else None
        nonconv = len(re.findall(r"did NOT converge", text))
    elif lin["TotalSolves"] == 1:
        per_solve = lin["TotalIts"]
        nonconv = int(lin["TotalIts"] >= 400)   # single solve at the MaxIts limit
    return dict(dof=j["Problem"]["DegreesOfFreedom"], its=lin["TotalIts"], solves=lin["TotalSolves"],
                max_its=per_solve, nonconv=nonconv, time=j["ElapsedTime"]["Durations"]["Total"],
                ram=j["PeakMemoryMegabytes"]["Total"] / 1024, git=j.get("GitTag"),
                s=read_port_s(glob.glob(os.path.join(data_dir, "output", "*", "port-S.csv"))[0]))


def fmt_time(sec):
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def max_ds(a, b):
    fa, sa = a
    fb, sb = b
    f = np.intersect1d(np.round(fa, 9), np.round(fb, 9))
    ia = np.isin(np.round(fa, 9), f)
    ib = np.isin(np.round(fb, 9), f)
    return max(float(np.max(np.abs(sa[k][ia] - sb[k][ib]))) for k in sa)


print("| Model | DOF | Its/solve off → on | Max its off → on | Time off → on | Speed-up | Peak RAM off → on | RAM factor | max\\|ΔS\\| |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
tot_old = tot_new = 0.0
for d in sorted(glob.glob(os.path.join(NEW, "*_data"))):
    name = os.path.basename(d)[:-5]
    new, old = run(d), run(os.path.join(OLD, name + "_data"))
    if new is None or old is None:
        print(f"| {name} | (not run yet) ||||||||")
        continue
    assert new["dof"] == old["dof"], name
    tot_old += old["time"]; tot_new += new["time"]
    mx_old = "?" if old["max_its"] is None else f"{old['max_its']}{' (NC)' if old['nonconv'] else ''}"
    mx_new = f"{new['max_its']}{' (NC %d)' % new['nonconv'] if new['nonconv'] else ''}"
    print(f"| {name} | {new['dof']:,} | {old['its'] / old['solves']:.0f} → {new['its'] / new['solves']:.0f} | "
          f"{mx_old} → {mx_new} | {fmt_time(old['time'])} → {fmt_time(new['time'])} | "
          f"{old['time'] / new['time']:.1f}x | {old['ram']:.1f} → {new['ram']:.1f} GB | "
          f"{new['ram'] / old['ram']:.2f} | {max_ds(old['s'], new['s']):.1e} |")
if tot_new:
    print(f"\nTotal solve time of the models run so far: {fmt_time(tot_old)} → {fmt_time(tot_new)} "
          f"({tot_old / tot_new:.1f}x)")
