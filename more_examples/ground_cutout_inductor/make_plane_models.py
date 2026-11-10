"""Generates the no-cutout models, one after another (runs with one layout file must not overlap), and prints how finely
the plane is meshed under the coil and outside it, because a solid plane has no metal edges there to refine at.
"""
import json
import os
import subprocess
import sys

import gmsh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
COILS = {"L0n5": 87.1, "L2n0": 147.7}
LAYER = {"M1": "Metal1", "M3": "Metal3"}


def sweep_runs():
    """name, coil, margin (outer size of the plane), plane layer, fpoint, amr passes.

    A smaller cell size on the plane's layer only refines along its outer edges, not under the coil. So the mesh check is
    Palace AMR at single frequencies, which refines wherever its error estimate says, also inside the plane. These two
    runs are enough for the report's statement; AMR on the 2 nH coil reaches the memory limit of a 128 GB machine."""
    runs = [(f"s_{c}_g{g}_plane{p}", c, g, p, "", "") for c in COILS for g in (30, 150) for p in LAYER]
    runs.append(("amr_L0n5_planeM1_f5", "L0n5", 30, "M1", "5e9", "3"))
    runs.append(("amr_L0n5_planeM1_fh", "L0n5", 30, "M1", "20e9", "3"))
    return runs


def plane_mesh(name, plane, D):
    path = os.path.join(HERE, "palace_model", f"{name}_data", f"{name}.msh")
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.open(path)
    total = len(gmsh.model.mesh.getNodes()[0])
    groups = {gmsh.model.getPhysicalName(d, t): (d, t) for d, t in gmsh.model.getPhysicalGroups()}
    coords = gmsh.model.mesh.getNodesForPhysicalGroup(*groups[LAYER[plane]])[1].reshape(-1, 3)
    gmsh.finalize()
    top = coords[coords[:, 2] > coords[:, 2].max() - 1e-3]
    half = D / 2
    under = (abs(top[:, 0]) < half) & (abs(top[:, 1]) < half)
    spacing = lambda count, area: (area / max(count, 1)) ** 0.5
    plane_half = abs(top[:, 0]).max()
    return (total, spacing(under.sum(), (2 * half) ** 2),
            spacing((~under).sum(), (2 * plane_half) ** 2 - (2 * half) ** 2))


if __name__ == "__main__":
    selected = sys.argv[1:]
    for name, coil, gap, plane, fpoint, amr in sweep_runs():
        if selected and name not in selected:
            continue
        log = os.path.join(HERE, "palace_model", f"{name}.log")
        with open(log, "w") as out:
            code = subprocess.run([sys.executable, "-u", os.path.join(HERE, "study.py"), name, coil, str(COILS[coil]),
                                   str(gap), f"plane_{plane}", fpoint, "", "", "", amr], stdout=out, stderr=subprocess.STDOUT,
                                  cwd=HERE).returncode
        if code:
            print(f"{name:24s} FAILED, exit {code}, see {log}")
            continue
        if amr:   # direct solves: gds2palace writes the fast sweep's tolerance also for single frequencies
            config = os.path.join(HERE, "palace_model", f"{name}_data", "config.json")
            with open(config) as source:
                data = json.load(source)
            data["Solver"]["Driven"]["AdaptiveTol"] = 0
            with open(config, "w", newline="\n") as target:
                json.dump(data, target, indent=2)
        nodes, under, outside = plane_mesh(name, plane, COILS[coil])
        print(f"{name:24s} nodes {nodes:7d}   plane spacing under coil {under:5.1f} um, outside {outside:5.1f} um", flush=True)
