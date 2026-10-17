"""Shared helpers of the conductor model study: Palace results to scikit-rf networks, and the cost of a run.

results/<model>/ holds port-S.csv, palace.json, run.log and config.json of each run (remote_runs.py collect).
"""
import os
import re

import numpy as np
import skrf as rf

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, 'results')
MESH_STUDIES = os.path.join(HERE, '..', 'mesh_convergence')


def palace_network(name, folder=RESULTS):
    """scikit-rf network from a Palace port-S.csv (raw S-parameters, no de-embedding, same as the mesh study snp files)"""
    path = os.path.join(folder, name, 'port-S.csv')
    header = open(path).readline().split(',')
    a = np.loadtxt(path, delimiter=',', skiprows=1, ndmin=2)
    a = a[np.argsort(a[:, 0])]
    idx = [tuple(int(x) for x in re.findall(r'\[(\d+)\]', h)) for h in header]
    n = max(i for k in idx if len(k) == 2 for i in k)
    s = np.zeros((len(a), n, n), complex)
    for col, k in enumerate(idx):
        if len(k) == 2 and header[col].strip().startswith('|S'):
            s[:, k[0] - 1, k[1] - 1] = 10 ** (a[:, col] / 20) * np.exp(1j * np.deg2rad(a[:, col + 1]))
    return rf.Network(frequency=rf.Frequency.from_f(a[:, 0], unit='GHz'), s=s, z0=50, name=name)


def reference_network(study, fname):
    """reference result of a mesh convergence study (Touchstone file in its results/snp folder)"""
    return rf.Network(os.path.join(MESH_STUDIES, study, 'results', 'snp', fname))


def cost(name, folder=RESULTS):
    """unknowns (finest level), run time (min), peak memory (GB), GMRES iterations per solve, linear solves"""
    log = open(os.path.join(folder, name, 'run.log'), errors='replace').read()
    unknowns = max(int(x) for x in re.findall(r'Level \d+ \(p = \d+\): (\d+) unknowns', log))
    total = float(re.findall(r'^Total\s+([\d.]+)\s', log, re.M)[-1])
    mem = re.search(r'Peak Memory.*?^Total\s+([\d.]+)([KMG])', log, re.M | re.S)
    peak_gb = float(mem.group(1)) * {'K': 1e-6, 'M': 1e-3, 'G': 1}[mem.group(2)]
    its = [int(x) for x in re.findall(r'GMRES solver converged in (\d+) iterations', log)]
    return dict(unknowns=unknowns, minutes=total / 60, peak_gb=peak_gb,
                its_per_solve=float(np.mean(its)) if its else np.nan, solves=len(its))


def at(ntw, values, f_hz):
    return np.interp(f_hz, ntw.f, values)


def deembedded(ntw, port_info_path):
    """remove the series inductance of the port sheets, as scripts/combine_extend_snp.py does for the *_deembedded files
    (the reference Touchstone files of the mesh convergence studies are de-embedded this way)"""
    import json
    import sys
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
    from combine_extend_snp import flat_strip_inductance
    from skrf.circuit import Circuit
    info = json.load(open(port_info_path))
    unit = info.get('unit', 1e-6)
    lport = {p['portnumber']: flat_strip_inductance(p['length'], p['width'], 0, unit) for p in info['ports']
             if p.get('length') is not None and p.get('width') is not None}
    media = rf.media.DefinedGammaZ0(frequency=ntw.frequency, z0=50)
    dut = ntw.copy()
    dut.name = 'dut'
    connections = []
    for n in range(ntw.nports):
        ind = media.inductor(L=-lport.get(n + 1, 0.0), name=f'L{n + 1}')
        port = Circuit.Port(ntw.frequency, name=f'P{n + 1}', z0=dut.z0[:, n])
        connections += [[(port, 0), (ind, 0)], [(ind, 1), (dut, n)]]
    return Circuit(connections).network
