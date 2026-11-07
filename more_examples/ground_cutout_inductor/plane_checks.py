"""Checks of the no-cutout runs that don't rely on the sweep mesh.

1. AMR: values at single frequencies on each refinement pass against the sweep.
2. L against frequency: free value at low frequency, image limit at high frequency.
   Image limit: a good conductor mirrors the coil, so L = L_free - M(coil, its image at twice the height), with M from
   the Neumann integral over the centre lines of the turns.
3. Shunt capacitance times height: constant if the plane or the silicon acts as a plate below the coil.
"""
import csv
import glob
import os

import numpy as np

import analyze
import trend

HERE =os.path.dirname(os.path.abspath(__file__))
COILS = {"L0n5": dict(N=2, D=87.1), "L2n0": dict(N=3, D=147.7)}
W, S = 5.0, 2.0
MU0 = 4e-7 * np.pi
STACK = os.path.join(HERE, "palace_model", "s_L0n5_g30_planeM1_data", "s_L0n5_g30_planeM1.msh")


def read_s(path):
    """Frequencies, Y matrices, or None if the file holds no complete row (a run killed during that pass)."""
    rows = [r for r in csv.reader(open(path)) if r]
    if len(rows) < 2:
        return None
    head = [h.strip() for h in rows[0]]
    try:
        data = np.array([[float(x) for x in r] for r in rows[1:]])
    except ValueError:
        return None
    if np.isnan(data).any():
        return None
    s = np.zeros((len(data), 2, 2), complex)
    for a in (1, 2):
        for b in (1, 2):
            db = [i for i, h in enumerate(head) if f"S[{a}][{b}]" in h and "dB" in h][0]
            arg = [i for i, h in enumerate(head) if f"S[{a}][{b}]" in h and "arg" in h][0]
            s[:, a - 1, b - 1] = 10 ** (data[:, db] / 20) * np.exp(1j * np.radians(data[:, arg]))
    identity = np.eye(2)
    return data[:, 0] * 1e9, np.array([np.linalg.inv(identity + m) @ (identity - m) / 50.0 for m in s])


def unknowns(name):
    log = os.path.join(HERE, "results", f"{name}_data", "palace.log")
    return [int(line.split(":")[1].split()[0]) for line in open(log, errors="replace") if "Level 1 (p = 2):" in line]


def amr_table():
    print("1. AMR, change against the sweep on the base mesh, in %")
    for coil, plane, tag in (("L0n5", "M1", "f5"), ("L0n5", "M1", "fh")):
        name = f"amr_{coil}_plane{plane}_{tag}"
        sweep = f"s_{coil}_g30_plane{plane}"
        f0, y0 = analyze.read_y(sweep)
        ref = analyze.values(f0, y0)
        base = os.path.join(HERE, "results", f"{name}_data", "output")
        folder = glob.glob(os.path.join(base, "*"))[0]
        paths = sorted(glob.glob(os.path.join(folder, "iteration*", "port-S.csv"))) + [os.path.join(folder, "port-S.csv")]
        sizes = unknowns(name)
        print(f"  {name}")
        for k, path in enumerate(paths):
            result = read_s(path)
            if result is None:
                print(f"    pass {k + 1}: {sizes[k] if k < len(sizes) else '?':>9} unknowns, no result (run stopped)")
                continue
            f, y = result
            v = analyze.values(f, y)
            i = int(np.argmin(np.abs(f0 - f[0])))
            rel = lambda key: 100 * (v[key][0] - ref[key][i]) / abs(ref[key][i])
            print(f"    pass {k + 1}: {sizes[k]:>9} unknowns at {f[0] / 1e9:4.0f} GHz  L {rel('L_diff'):+6.2f}  R {rel('R_diff'):+6.2f}"
                  f"  Q {rel('Q_diff'):+6.2f}  C {rel_c(v, y, f, ref, y0, f0, i):+6.2f}")


def rel_c(v, y, f, ref, y0, f0, i):
    return 100 * (v["y_cm"][0].imag / f[0] - ref["y_cm"][i].imag / f0[i]) / (ref["y_cm"][i].imag / f0[i])


def octagon(radius, n=400):
    """Closed octagon with this apothem, points and segment vectors, in meter."""
    corners = []
    for k in range(8):
        angle = np.pi / 8 + k * np.pi / 4
        corners.append([radius / np.cos(np.pi / 8) * np.cos(angle), radius / np.cos(np.pi / 8) * np.sin(angle)])
    corners = np.array(corners + corners[:1]) * 1e-6
    points = np.vstack([corners[i] + (corners[i + 1] - corners[i]) * t for i in range(8)
                        for t in (np.arange(n // 8) + 0.5) / (n // 8)])
    steps = np.vstack([np.tile((corners[i + 1] - corners[i]) / (n // 8), (n // 8, 1)) for i in range(8)])
    return points, steps


def mutual(a, b, distance):
    """Neumann integral between two parallel loops, distance in meter."""
    pa, da = a
    pb, db = b
    r = np.sqrt(((pa[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2) + distance ** 2)
    return MU0 / (4 * np.pi) * ((da @ db.T) / r).sum()


def image_mutual(coil, height_um):
    data = COILS[coil]
    loops = [octagon(data["D"] / 2 - W / 2 - k * (W + S)) for k in range(data["N"])]
    return sum(mutual(a, b, 2 * height_um * 1e-6) for a in loops for b in loops)


def heights():
    """Height of the coil's TopMetal2 middle over the top of Metal1 and Metal3, and over the silicon, in um."""
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.open(STACK)
    groups = {gmsh.model.getPhysicalName(d, t): (d, t) for d, t in gmsh.model.getPhysicalGroups()}
    z = lambda group: gmsh.model.mesh.getNodesForPhysicalGroup(*groups[group])[1].reshape(-1, 3)[:, 2]
    z_top = z("TopMetal2")
    z_m1 = z("Metal1")
    gmsh.finalize()
    middle = (z_top.min() + z_top.max()) / 2
    m1_top = z_m1.max()
    # from the stackup: Metal1 0.42, Via1 0.54, Metal2 0.49, Via2 0.54, Metal3 0.49; Metal1 sits on Cont, on Activ top
    return dict(M1=middle - m1_top, M3=middle - (m1_top + 0.54 + 0.49 + 0.54 + 0.49), middle=middle, m1_top=m1_top)


def l_table(h):
    print("\n2. Differential L in nH: free value at low frequency, image limit at high frequency")
    frequencies = [0.1e9, 0.3e9, 1e9, 3e9, 5e9, 10e9, 20e9]
    print(f"  {'run':22s}" + "".join(f"{x / 1e9:7.1f}" for x in frequencies) + "   L_free - M(image)")
    for coil in COILS:
        f, y = analyze.read_y(f"s_{coil}_g150_float")
        v = analyze.values(f, y)
        free = analyze.at(f, v["L_diff"], 0.1e9)
        print(f"  {coil + ' frame 150':22s}" + "".join(f"{analyze.at(f, v['L_diff'], x) * 1e9:7.3f}" for x in frequencies))
        for plane in ("M1", "M3"):
            f, y = analyze.read_y(f"s_{coil}_g150_plane{plane}")
            v = analyze.values(f, y)
            limit = free - image_mutual(coil, h[plane])
            print(f"  {coil + ' plane ' + plane:22s}" + "".join(f"{analyze.at(f, v['L_diff'], x) * 1e9:7.3f}" for x in frequencies)
                  + f"   {limit * 1e9:.3f} (height {h[plane]:.2f} um)")


def c_table(h):
    print("\n3. Shunt C at 2.4 GHz, fF, and C times the height of the coil over the plane")
    for coil in COILS:
        for plane in ("M1", "M3"):
            f, y = analyze.read_y(f"s_{coil}_g150_plane{plane}")
            v = analyze.values(f, y)
            c = analyze.at(f, v["y_cm"].imag / (2 * np.pi * f), 2.4e9) * 1e15
            print(f"  {coil} {plane}: C {c:6.1f}, height {h[plane]:5.2f}, C*h {c * h[plane]:6.0f}")


def percent_table():
    """Change against the floating frame at 150 um, in %. Plane sizes 30 and 150 are the outer size of the frame there."""
    keys = [("L1", 1), ("L5", 1), ("R1", 1), ("R5", 1), ("Q5", 1), ("Qp", 1), ("SRF", 1), ("SRFse", 1), ("Qse", 1), ("C24", 1), ("G24", 1)]
    print("\n4. Change against the floating frame at 150 um, in %; absolute peak Q and frequency at the end")
    print(f"  {'run':24s}" + "".join(f"{k:>8s}" for k, _ in keys) + "      Qp    fQ    C24     G24")
    for coil in COILS:
        ref = trend.row(f"s_{coil}_g150_float")
        for name in (f"s_{coil}_g150_float", f"s_{coil}_g30_float", f"s_{coil}_g30_planeM1", f"s_{coil}_g150_planeM1",
                     f"s_{coil}_g30_planeM3", f"s_{coil}_g150_planeM3"):
            row = trend.row(name)
            print(f"  {name:24s}" + "".join(f"{100 * (row[k] - ref[k]) / ref[k]:+8.1f}" for k, _ in keys)
                  + f"  {row['Qp']:6.2f} {row['fQ']:5.1f} {row['C24']:6.1f} {row['G24']:7.4f}")


if __name__ == "__main__":
    amr_table()
    h = heights()
    l_table(h)
    c_table(h)
    percent_table()
