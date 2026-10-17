"""Accuracy and cost of the conductor models for every structure of the study.

Accuracy: each run against the most accurate existing result of that structure (the reference), with the figures of
merit of the original study, computed with that study's own functions (results/story_plots.py of each mesh convergence
study). Cost: unknowns, run time, peak memory, GMRES iterations per solve and number of solves, all from hpz2 with
16 MPI processes, one run at a time (the references ran under other conditions, so their run times are not used).
Writes results/tables.md and results/summary.json.  Usage (palace venv):  python analyze.py
"""
import importlib.util
import json
import os

import numpy as np
import skrf as rf

import study_data as D

HERE = D.HERE
MODELS = [('surface', 'surface_mesh2'), ('solve_inside', 'solve_inside_mesh2'),
          ('solve_inside_skin', 'solve_inside_skin_mesh2'), ('solve_inside_skin, 3 um', 'solve_inside_skin_mesh3'),
          ('solve_inside_skin, 5 um', 'solve_inside_skin_mesh5')]


def study_module(study):
    path = os.path.join(D.MESH_STUDIES, study, 'results', 'story_plots.py')
    spec = importlib.util.spec_from_file_location(f'story_plots_{study}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_network(name, deembed):
    ntw = D.palace_network(name)
    if deembed:
        ntw = D.deembedded(ntw, os.path.join(D.RESULTS, name, 'port_information.json'))
    return ntw


def pct(x, ref):
    return 100 * (x / ref - 1)


def below_srf(q):
    """index range below the first zero crossing of Q (self-resonance)"""
    neg = np.where(q <= 0)[0]
    return slice(1, neg[0] if len(neg) else len(q))


def peak(f, q):
    sl = below_srf(q)
    i = np.argmax(q[sl])
    return q[sl][i], f[sl][i]


# ---------------------------------------------------------------- figures of merit per structure

def inductor_merits(S, ntw):
    m = S.lqr(ntw)
    qpk, fpk = peak(ntw.f, m['Q'])
    return {'R at 1 GHz': D.at(ntw, m['R'], 1e9), 'L at 10 GHz': D.at(ntw, m['L'], 10e9), 'peak Q': qpk,
            'f peak Q (GHz)': fpk / 1e9}


def transformer_merits(S, ntw):
    m = S.coil(ntw)
    out = {k: D.at(ntw, m[v], S.F_DESIGN) for k, v in (('Lp at 30 GHz', 'Lp'), ('k at 30 GHz', 'k'),
                                                       ('Qp at 30 GHz', 'Qp'), ('Qs at 30 GHz', 'Qs'))}
    out['peak Qp'], out['peak Qs'] = peak(ntw.f, m['Qp'])[0], peak(ntw.f, m['Qs'])[0]
    return out


def balun2x1_merits(S, ntw):
    m = S.merits(ntw)
    lim = ntw.f <= S.F_COIL_MAX
    return {'Lp at 10 GHz': D.at(ntw, m['Lp'], S.L_FREQ), 'k at 10 GHz': D.at(ntw, m['k'], S.L_FREQ),
            'peak Qp': m['Qp'][lim].max(), 'peak Qs': m['Qs'][lim].max(), 'peak |Sdd21| (dB)': m['Sdd21'].max()}


def dband_merits(S, ntw):
    m = S.merits(ntw)
    b = (ntw.f >= S.BAND[0]) & (ntw.f <= S.BAND[1])
    return {'IL min (dB)': m['IL'][b].min(), 'IL max (dB)': m['IL'][b].max(), 'S11 null (GHz)': ntw.f[np.argmin(m['S11'])] / 1e9,
            'max |amp. imbalance| (dB)': np.abs(m['amp'][b]).max(), 'max |phase imbalance| (deg)': np.abs(m['phase'][b]).max(),
            '_IL': m['IL'][b]}


def mim_merits(S, ntw):
    m = S.merits(ntw)
    return {'IL min (dB)': m['IL'].min(), 'IL max (dB)': m['IL'].max(), 'worst |Sss11| (dB)': m['Sss11'].max(),
            'match null (GHz)': ntw.f[np.argmin(m['Sss11'])] / 1e9, '_IL': m['IL']}


STRUCTURES = {   # folder: (mesh study, reference file, de-embed, merits, relative quantities in %)
    'inductor': ('mesh_convergence_inductor', 'ind_frame_skin_mesh1.s2p', True, inductor_merits,
                 ['R at 1 GHz', 'L at 10 GHz', 'peak Q']),
    'transformer': ('mesh_convergence_transformer', 'transformer_skin_mesh1.s5p', True, transformer_merits,
                    ['Lp at 30 GHz', 'k at 30 GHz', 'Qp at 30 GHz', 'Qs at 30 GHz', 'peak Qp', 'peak Qs']),
    'balun2x1': ('mesh_convergence_balun2x1', 'balun2x1_skin_mesh1.s4p', True, balun2x1_merits,
                 ['Lp at 10 GHz', 'k at 10 GHz', 'peak Qp', 'peak Qs', 'peak |Sdd21| (dB)']),
    'dband_balun': ('mesh_convergence_D-band_balun', 'balun_skin_mesh1.s3p', True, dband_merits, []),
    'mim_balun': ('mesh_convergence_balun_mim', 'trans_100diff_to_80se_ports_skin_mesh1.s3p', False, mim_merits, []),
}
PREFIX = {'inductor': 'ind_frame', 'transformer': 'transformer', 'balun2x1': 'balun2x1', 'dband_balun': 'dband_balun',
          'mim_balun': 'mim_balun'}


def analyze_structure(folder):
    study, ref_file, deembed, merits, rel = STRUCTURES[folder]
    S = study_module(study)
    ref = D.reference_network(study, ref_file)
    rm = merits(S, ref)
    rows = []
    for label, suffix in MODELS:
        name = f'{PREFIX[folder]}_{suffix}'
        if not os.path.exists(os.path.join(D.RESULTS, name, 'run.log')):
            continue
        ntw = run_network(name, deembed)
        m = merits(S, ntw)
        row = {'model': label, 'name': name, **D.cost(name)}
        for k, v in m.items():
            if k.startswith('_'):
                continue
            row[k] = v
            if k in rel and '(dB)' in k:
                row['d ' + k] = v - rm[k]
            elif k in rel:
                row['d ' + k + ' (%)'] = pct(v, rm[k])
        if '_IL' in m:
            il = m['_IL'] if len(ntw.f) == len(ref.f) else np.interp(ref.f, ntw.f, m['_IL'])
            row['largest IL difference (dB)'] = float((il - rm['_IL'])[np.argmax(np.abs(il - rm['_IL']))])
        rows.append(row)
    return {'reference': {'file': f'{study}/results/snp/{ref_file}', **{k: v for k, v in rm.items() if not k.startswith('_')}},
            'runs': rows}


def table(title, data):
    rows = data['runs']
    keys = [k for k in rows[0] if k not in ('model', 'name')] if rows else []
    out = [f'### {title}', '', f"Reference: `{data['reference']['file']}`: " +
           ', '.join(f'{k} {v:.4g}' for k, v in data['reference'].items() if k != 'file'), '',
           '| model | ' + ' | '.join(keys) + ' |', '|---|' + '---:|' * len(keys)]
    for r in rows:
        out.append(f"| {r['model']} | " + ' | '.join(fmt(k, r.get(k)) for k in keys) + ' |')
    return out + ['']


def fmt(k, v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ''
    if k == 'unknowns':
        return f'{v / 1e6:.2f} M'
    if k.startswith('d ') or 'difference' in k:
        return f'{v:+.2f}' if 'dB' in k else f'{v:+.1f}'
    if k in ('minutes',):
        return f'{v:.1f}'
    if k == 'solves':
        return f'{v:d}'
    return f'{v:.3g}' if isinstance(v, float) else str(v)


def main():
    summary, lines = {}, ['# Conductor model study: tables', '']
    for folder in STRUCTURES:
        data = analyze_structure(folder)
        if data['runs']:
            summary[folder] = data
            lines += table(folder, data)
    import analyze_lines
    import analyze_l6n2
    summary['lines'] = analyze_lines.analyze()
    lines += analyze_lines.table(summary['lines'])
    summary['l6n2'] = analyze_l6n2.analyze()
    lines += analyze_l6n2.table(summary['l6n2'])
    json.dump(summary, open(os.path.join(D.RESULTS, 'summary.json'), 'w'), indent=1, default=float)
    open(os.path.join(D.RESULTS, 'tables.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
