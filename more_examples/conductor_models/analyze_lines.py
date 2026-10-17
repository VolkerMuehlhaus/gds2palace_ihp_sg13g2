"""Straight TopMetal2 lines (lines/make_line_models.py): line constants from two line lengths, per conductor model.

For lengths L1 < L2 with identical port transitions P1, P2:  ABCD(L) = P1 * LINE(L) * P2, so
M = ABCD(L2) * ABCD(L1)^-1 = P1 * LINE(L2 - L1) * P1^-1 has the eigenvalues exp(+-gamma (L2 - L1)), independent of the
ports. Two results per line and frequency:
  - attenuation alpha = Re(gamma) in dB/mm, compared with the converged filled model (refined_cellsize 0.25 um,
    lines/reference/*_fill025): what a designer sees in |S21|
  - line resistance R', compared with the 2D filament calculation (lines/peec2d.py). With lossless dielectrics,
    gamma^2 = (R' + j w L') j w C', so Q_line = w L'/R' = -Re(gamma^2)/Im(gamma^2) needs no characteristic impedance;
    R' = w L'_2D (1/Q_line - 1/Q_other), where 1/Q_other are the losses outside the conductor (radiation, absorbing
    boundary, silicon beside the ground plate), measured on the same lines with ideal conductors (reference/*_pec2).
Usage: imported by analyze.py, or  python analyze_lines.py
"""
import os
import sys

import numpy as np
import skrf as rf

import study_data as D

LINES = os.path.join(D.HERE, 'lines')
sys.path.insert(0, LINES)
import make_line_models as M   # noqa: E402
import peec2d                  # noqa: E402

SIGMA, T, H = 30.3e6, 3.0, 195.1003 - 183.87          # TopMetal2, height of its bottom above SUBGND (um)
DL = (M.LENGTHS[1] - M.LENGTHS[0]) * 1e-6
LABELS = {'surface_mesh2': 'surface', 'solve_inside_mesh2': 'solve_inside', 'solve_inside_skin_mesh2': 'solve_inside_skin',
          'solve_inside_skin_mesh5': 'solve_inside_skin, 5 um'}


def gamma(w, model, folder=D.RESULTS):
    names = [M.name_of(w, L, model) for L in M.LENGTHS]
    if not all(os.path.exists(os.path.join(folder, n, 'port-S.csv')) for n in names):
        return None, None
    n1, n2 = (D.palace_network(n, folder) for n in names)
    A1, A2 = rf.network.s2a(n1.s, z0=50), rf.network.s2a(n2.s, z0=50)
    g = []
    for a1, a2 in zip(A1, A2):
        lg = np.log(np.linalg.eigvals(a2 @ np.linalg.inv(a1))) / DL
        g.append(lg[np.argmax(lg.real)])          # the growing root: +gamma (Re > 0)
    return n1.f, np.array(g)


def analyze():
    ref_dir = os.path.join(LINES, 'reference')
    rows = []
    for w in M.WIDTHS:
        f, g_ref = gamma(w, 'fill025', ref_dir)
        _, g_pec = gamma(w, 'pec2', ref_dir)
        g2p = g_pec ** 2
        invq_other = -g2p.imag / g2p.real
        z2d = peec2d.Strip(w, T, H, SIGMA).Z(f)
        om = 2 * np.pi * f
        l2d = z2d.imag / om
        alpha_ref = 20 / np.log(10) * g_ref.real / 1e3
        for model, label in LABELS.items():
            fm, g = gamma(w, model)
            if g is None:
                continue
            assert np.allclose(fm, f)
            g2 = g ** 2
            r = om * l2d * (-g2.real / g2.imag) ** -1
            r_cond = om * l2d * (1 / (-g2.real / g2.imag) - invq_other)
            alpha = 20 / np.log(10) * g.real / 1e3
            rows.append({'w (um)': w, 'model': label, 'name': M.name_of(w, M.LENGTHS[1], model),
                         'f (GHz)': list(f / 1e9), "R'/R'_2D": list(r_cond / z2d.real),
                         'alpha (dB/mm)': list(alpha), 'alpha_ref (dB/mm)': list(alpha_ref),
                         'd alpha (dB/mm)': list(alpha - alpha_ref), 'd alpha (%)': list(100 * (alpha / alpha_ref - 1)),
                         **{k: D.cost(M.name_of(w, L, model))[k] for L in M.LENGTHS[1:]
                            for k in ('unknowns', 'minutes', 'peak_gb', 'its_per_solve')}})
    return rows


def table(rows):
    if not rows:
        return []
    fs = rows[0]['f (GHz)']
    out = ['### lines', '',
           "Line resistance R' (corrected for the losses outside the conductor) divided by R' of the 2D calculation, "
           'and the attenuation error against the filled 0.25 um model in dB/mm. Cost of the 300 um line.', '',
           "| w (um) | model | quantity | " + ' | '.join(f'{x:g} GHz' for x in fs[1:]) + ' | unknowns | minutes | peak GB |',
           '|---|---|---|' + '---:|' * (len(fs) - 1) + '---:|---:|---:|']
    for r in rows:
        out.append(f"| {r['w (um)']} | {r['model']} | R'/R'_2D | " + ' | '.join(f'{x:.3f}' for x in r["R'/R'_2D"][1:]) +
                   f" | {r['unknowns'] / 1e6:.2f} M | {r['minutes']:.1f} | {r['peak_gb']:.1f} |")
        out.append(f"| | | d alpha (dB/mm) | " + ' | '.join(f'{x:+.3f}' for x in r['d alpha (dB/mm)'][1:]) + ' | | | |')
    return out + ['']


if __name__ == '__main__':
    print('\n'.join(table(analyze())))
