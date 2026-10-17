"""Figures of the conductor model study README (results/plots/*.png). Run after analyze.py (palace venv):
    python plots.py
Colors: categorical slots 1-4 of the reference palette in fixed order (surface blue, solve_inside orange,
solve_inside_skin aqua), each with its own line style and marker; the reference is ink.
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import skrf as rf

import analyze as A
import analyze_l6n2 as L6
import analyze_lines as AL
import study_data as D

OUT = os.path.join(D.RESULTS, 'plots')
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3de'
STYLE = {   # model label: (color, line style, marker)
    'surface': ('#2a78d6', '-', 'o'),
    'solve_inside': ('#eb6834', '--', 's'),
    'solve_inside_skin': ('#1baf7a', '-', 'D'),
    'solve_inside_skin, 3 um': ('#1baf7a', ':', 'D'),
    'solve_inside_skin, 5 um': ('#1baf7a', ':', 'D'),
}
TITLES = {'inductor': 'Spiral inductor', 'transformer': 'Transformer (30 GHz)', 'balun2x1': '2:1 balun',
          'dband_balun': 'D-band balun', 'mim_balun': 'MIM-loaded balun', 'l6n2': 'L6n2 (vs. measurement)'}


def style(ax, title=None):
    ax.grid(True, color=GRID, linewidth=0.8)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    if title:
        ax.set_title(title, loc='left', fontsize=11, color=INK)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name), dpi=130, facecolor='white')
    plt.close(fig)
    print('wrote', name)


def summary():
    return json.load(open(os.path.join(D.RESULTS, 'summary.json')))


def surface_minutes(runs):
    return next(r['minutes'] for r in runs if r['model'] == 'surface')


# ------------------------------------------------------------------ figure 1: accuracy against cost

def fig_accuracy_vs_cost(S):
    """loss error of each model against its run time relative to the surface model of the same structure"""
    panels = [('Coil Q error at its peak', [('inductor', 'd peak Q (%)'), ('transformer', 'd peak Qp (%)'),
                                            ('balun2x1', 'd peak Qp (%)'), ('l6n2', 'd peak Q vs. measured (%)')], '%'),
              ('Insertion loss error of the baluns', [('dband_balun', 'largest IL difference (dB)'),
                                                     ('mim_balun', 'largest IL difference (dB)')], 'dB')]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    marker_struct = {'inductor': 'o', 'transformer': 's', 'balun2x1': '^', 'l6n2': 'P', 'dband_balun': 'o', 'mim_balun': 's'}
    for ax, (title, items, unit) in zip(axes, panels):
        for folder, key in items:
            runs = S[folder]['runs'] if folder != 'l6n2' else [r for r in S['l6n2']['runs'] if 'minutes' in r]
            t0 = surface_minutes(runs)
            for r in runs:
                if r['model'] not in STYLE or key not in r:
                    continue
                c = STYLE[r['model']][0]
                filled = ',' not in r['model']
                ax.scatter(r['minutes'] / t0, r[key], s=60, marker=marker_struct[folder],
                           facecolor=c if filled else 'white', edgecolor=c if not filled else 'white', linewidth=1.6,
                           zorder=3)
            ax.scatter([], [], marker=marker_struct[folder], color=INK2, label=TITLES[folder])
        ax.axhline(0, color=INK, linewidth=1)
        ax.set_xlabel('Run time relative to the surface model of the same structure', color=INK2)
        ax.set_ylabel(f'Error ({unit}), reference = 0', color=INK2)
        style(ax, title)
        ax.legend(fontsize=8, frameon=False, loc='best')
    handles = [plt.Line2D([], [], color=STYLE[m][0], marker='o', linestyle='', markersize=8, label=m)
               for m in ('surface', 'solve_inside', 'solve_inside_skin')]
    handles.append(plt.Line2D([], [], color=STYLE['solve_inside_skin'][0], marker='o', markerfacecolor='white',
                              linestyle='', markersize=8, label='solve_inside_skin, coarser mesh'))
    fig.legend(handles=handles, loc='upper center', ncol=5, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, 'accuracy_vs_cost.png')


# ------------------------------------------------------------------ figure 2: Q of the coils against frequency

def fig_coil_q():
    specs = [('inductor', 'lqr', 'Q', 'Spiral inductor: differential Q', 50e9),
             ('transformer', 'coil', 'Qp', 'Transformer: primary Q', 45e9),
             ('balun2x1', 'merits', 'Qp', '2:1 balun: primary Q', 25e9)]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, (folder, fn, key, title, fmax) in zip(axes, specs):
        study, ref_file, deembed, _, _ = A.STRUCTURES[folder]
        mod = A.study_module(study)
        get = getattr(mod, fn)
        ref = D.reference_network(study, ref_file)
        sel = ref.f <= fmax
        ax.plot(ref.f[sel] / 1e9, get(ref)[key][sel], color=INK, linewidth=2.2, label='reference (skin layers, 1 um)')
        for label, suffix in A.MODELS:
            name = f'{A.PREFIX[folder]}_{suffix}'
            if label not in STYLE or ',' in label or not os.path.exists(os.path.join(D.RESULTS, name, 'run.log')):
                continue
            ntw = A.run_network(name, deembed)
            sel = ntw.f <= fmax
            c, ls, _ = STYLE[label]
            ax.plot(ntw.f[sel] / 1e9, get(ntw)[key][sel], color=c, linestyle=ls, linewidth=2, label=label)
        ax.set_xlabel('Frequency (GHz)', color=INK2)
        ax.set_ylim(bottom=0)
        style(ax, title)
    axes[0].set_ylabel('Q', color=INK2)
    h, l = axes[1].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=5, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, 'coil_q.png')


# ------------------------------------------------------------------ figure 3: insertion loss of the baluns

def fig_balun_il():
    specs = [('mim_balun', 'MIM-loaded balun: insertion loss'), ('dband_balun', 'D-band balun: insertion loss')]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (folder, title) in zip(axes, specs):
        study, ref_file, deembed, _, _ = A.STRUCTURES[folder]
        mod = A.study_module(study)
        ref = D.reference_network(study, ref_file)
        band = getattr(mod, 'BAND', (ref.f[0], ref.f[-1]))
        sel = (ref.f >= band[0]) & (ref.f <= band[1])
        ax.plot(ref.f[sel] / 1e9, mod.merits(ref)['IL'][sel], color=INK, linewidth=2.2, label='reference (skin layers, 1 um)')
        for label, suffix in A.MODELS:
            name = f'{A.PREFIX[folder]}_{suffix}'
            if label not in STYLE or ',' in label or not os.path.exists(os.path.join(D.RESULTS, name, 'run.log')):
                continue
            ntw = A.run_network(name, deembed)
            sel = (ntw.f >= band[0]) & (ntw.f <= band[1])
            c, ls, _ = STYLE[label]
            ax.plot(ntw.f[sel] / 1e9, mod.merits(ntw)['IL'][sel], color=c, linestyle=ls, linewidth=2, label=label)
        ax.set_xlabel('Frequency (GHz)', color=INK2)
        ax.set_ylabel('Insertion loss (dB)', color=INK2)
        style(ax, title)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=5, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, 'balun_il.png')


# ------------------------------------------------------------------ figure 4: straight lines

def fig_lines(S):
    rows = S['lines']
    widths = sorted({r['w (um)'] for r in rows})
    fig, axes = plt.subplots(1, len(widths), figsize=(3.3 * len(widths) + 0.6, 4), sharey=True)
    for ax, w in zip(axes, widths):
        for r in rows:
            if r['w (um)'] != w or r['model'] not in STYLE:
                continue
            c, ls, mk = STYLE[r['model']]
            f = np.array(r['f (GHz)'])[1:]
            ax.plot(f, np.array(r["R'/R'_2D"])[1:], color=c, linestyle=ls, marker=mk, markersize=4, linewidth=1.8,
                    label=r['model'])
        ax.axhline(1, color=INK, linewidth=1)
        ax.axhspan(0.95, 1.05, color=GRID, alpha=0.6, linewidth=0)
        ax.set_xscale('log')
        ax.set_xlabel('Frequency (GHz)', color=INK2)
        style(ax, f'w = {w:g} um')
    axes[0].set_ylabel("Line resistance R' / 2D calculation", color=INK2)
    h, l = axes[-1].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=4, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, 'lines_R.png')


# ------------------------------------------------------------------ figure 5: L6n2 against the measurement

def fig_l6n2():
    def zq(ntw):
        z = ntw.z
        zd = z[:, 0, 0] - z[:, 0, 1] - z[:, 1, 0] + z[:, 1, 1]
        return zd.imag / zd.real
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    meas = rf.Network(L6.MEAS)
    sel = meas.f <= 12e9
    ax.plot(meas.f[sel] / 1e9, zq(meas)[sel], color=INK, linewidth=2.2, label='measured')
    for label, name in L6.MODELS:
        if label not in STYLE or not os.path.exists(os.path.join(D.RESULTS, name, 'run.log')):
            continue
        ntw = D.palace_network(name)
        sel = ntw.f <= 12e9
        c, ls, _ = STYLE[label]
        ax.plot(ntw.f[sel] / 1e9, zq(ntw)[sel], color=c, linestyle=ls, linewidth=2, label=label)
    ax.set_ylim(bottom=0)
    ax.set_xlabel('Frequency (GHz)', color=INK2)
    ax.set_ylabel('Differential Q', color=INK2)
    style(ax, 'L6n2: differential Q, 2 um mesh')
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    save(fig, 'l6n2_q.png')


if __name__ == '__main__':
    S = summary()
    fig_accuracy_vs_cost(S)
    fig_coil_q()
    fig_balun_il()
    fig_lines(S)
    fig_l6n2()
