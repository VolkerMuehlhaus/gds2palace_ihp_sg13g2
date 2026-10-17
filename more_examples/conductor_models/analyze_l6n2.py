"""L6n2 inductor (4 turns) against the measurement, with the setup of the L6n2 v3 study (conformal passivation, via
merging with fill factor correction, 400 um margin). Differential impedance Zdiff = Z11 - Z12 - Z21 + Z22:
L = Im(Zdiff)/w at 1 GHz, peak Q = max of Im(Zdiff)/Re(Zdiff), SRF = first zero crossing of Im(Zdiff).
The L6n2 v3 filled metal runs at 2 and 1 um are shown for comparison (same model, earlier runs).
Usage: imported by analyze.py, or  python analyze_l6n2.py
"""
import os

import numpy as np
import skrf as rf

import study_data as D

V3 = os.path.join(D.HERE, '..', 'measured_vs_simulated', 'more_accurate_models_L6n2_v3')
MEAS = os.path.join(V3, 'meas_L5_6n2_THRU_deemb.S2P')
V3_RUNS = [("v3 study: 'solve_inside', 2 um", 'L6n2_with_ports_2um_passi3D.s2p'),
           ("v3 study: 'solve_inside', 1 um", 'L6n2_with_ports_1um_passi3D.s2p')]
MODELS = [('surface', 'l6n2_surface_mesh2'), ('solve_inside', 'l6n2_solve_inside_mesh2')]


def merits(ntw):
    z = ntw.z
    zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
    f = ntw.f
    q = zd.imag / zd.real
    cross = np.where((zd.imag[:-1] > 0) & (zd.imag[1:] <= 0))[0]
    i = cross[0] if len(cross) else None
    srf = f[i] - zd.imag[i] * (f[i + 1] - f[i]) / (zd.imag[i + 1] - zd.imag[i]) if i is not None else np.nan
    below = f < (srf if np.isfinite(srf) else np.inf)
    return {'L at 1 GHz (nH)': np.interp(1e9, f, zd.imag / (2 * np.pi * f)) * 1e9, 'peak Q': q[below].max(),
            'SRF (GHz)': srf / 1e9}


def analyze():
    meas = merits(rf.Network(MEAS))
    rows = []
    for label, fname in V3_RUNS:
        rows.append({'model': label, **merits(rf.Network(os.path.join(V3, 'results', fname)))})
    for label, name in MODELS:
        if os.path.exists(os.path.join(D.RESULTS, name, 'run.log')):
            rows.append({'model': label, 'name': name, **merits(D.palace_network(name)), **D.cost(name)})
    for r in rows:
        for k in meas:
            r['d ' + k.split(' (')[0] + ' vs. measured (%)'] = 100 * (r[k] / meas[k] - 1)
    return {'measured': meas, 'runs': rows}


def table(data):
    m = data['measured']
    keys = ['L at 1 GHz (nH)', 'peak Q', 'SRF (GHz)', 'd L at 1 GHz vs. measured (%)', 'd peak Q vs. measured (%)',
            'd SRF vs. measured (%)', 'unknowns', 'minutes', 'peak_gb', 'its_per_solve', 'solves']
    out = ['### l6n2', '', 'Measured: ' + ', '.join(f'{k} {v:.4g}' for k, v in m.items()), '',
           '| model | ' + ' | '.join(keys) + ' |', '|---|' + '---:|' * len(keys)]
    for r in data['runs']:
        cells = []
        for k in keys:
            v = r.get(k)
            if v is None:
                cells.append('')
            elif k == 'unknowns':
                cells.append(f'{v / 1e6:.2f} M')
            elif k.startswith('d '):
                cells.append(f'{v:+.1f}')
            elif k == 'solves':
                cells.append(f'{v:d}')
            else:
                cells.append(f'{v:.3g}')
        out.append(f"| {r['model']} | " + ' | '.join(cells) + ' |')
    return out + ['']


if __name__ == '__main__':
    print('\n'.join(table(analyze())))
