"""How well can a filled-metal FEM mesh resolve the skin effect? 1D model of the field across a TopMetal2 slab
(t = 3 um, sigma = 3.03e7 S/m) that carries current on both faces (symmetric, as a strip):
    d2E/dz2 = j w mu sigma E   for 0 < z < t,
driven by the same tangential magnetic field H0 at both faces. The surface impedance Zs = E(0)/H0 gives the conductor
loss for a given current; Re(Zs)/2 is the RF sheet resistance with both faces carrying current (DC: 1/(sigma t)).
Exact: Zs = (gamma/sigma) coth(gamma t/2).

FEM order 2 (as Palace order 2: the tangential field varies quadratically in the normal direction within a cell),
Galerkin with quadratic elements, on mesh lines through the thickness (the metal faces are always mesh lines):
2 um (2 cells of 1.5 um through the 3 um metal, as in the gds2palace mesh), 1 um (3 cells) and 0.5 um (6 cells).
This is the numerical scheme on a 1D slab, not a Palace run.
Writes plots/skin_1d_fem.png.  Run with Python (numpy, matplotlib):  python skin_1d_fem.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
MU0, SIGMA, T = 4e-7 * np.pi, 30.3e6, 3e-6


def exact(f, z):
    g = np.sqrt(2j * np.pi * f * MU0 * SIGMA)
    jwm = 2j * np.pi * f * MU0
    amp = jwm / (g * np.sinh(g * T / 2))                      # E = amp cosh(g (z - t/2)) for H0 = 1
    return amp * np.cosh(g * (np.asarray(z) - T / 2)), amp * np.cosh(g * T / 2)


def shape2(s):
    return np.array([2 * (s - 0.5) * (s - 1), -4 * s * (s - 1), 2 * s * (s - 0.5)])


def fem_p2(f, nodes):
    """quadratic elements on the given mesh lines; returns (z, E) at fine points and Zs"""
    k, jwm = 2j * np.pi * f * MU0 * SIGMA, 2j * np.pi * f * MU0
    ne = len(nodes) - 1
    n = 2 * ne + 1
    K = np.zeros((n, n), complex)
    gp, gw = np.polynomial.legendre.leggauss(4)
    for e in range(ne):
        h = nodes[e + 1] - nodes[e]
        idx = [2 * e, 2 * e + 1, 2 * e + 2]
        for xi, w in zip(gp, gw):
            s = (xi + 1) / 2
            N = shape2(s)
            dN = np.array([4 * s - 3, -8 * s + 4, 4 * s - 1]) / h
            K[np.ix_(idx, idx)] += (np.outer(dN, dN) + k * np.outer(N, N)) * w * h / 2
    rhs = np.zeros(n, complex)
    rhs[0] = rhs[-1] = jwm                                      # boundary terms of both faces
    E = np.linalg.solve(K, rhs)
    zs, Es = [], []
    for e in range(ne):
        s = np.linspace(0, 1, 60)
        zs += list(nodes[e] + s * (nodes[e + 1] - nodes[e]))
        Es += list(E[2 * e:2 * e + 3] @ shape2(s))
    return np.array(zs), np.array(Es), E[0]


MESHES = {'2 um': np.linspace(0, T, 3), '1 um': np.linspace(0, T, 4), '0.5 um': np.linspace(0, T, 7)}
COLORS = {'2 um': '#2a78d6', '1 um': '#1baf7a', '0.5 um': '#7a3db8'}

def figure(method, solve, meshes, filename, fr, ref):
    """current density at 75 GHz (left) and conductor loss over frequency (right) for one method"""
    f0 = 75e9
    delta = np.sqrt(2 / (2 * np.pi * f0 * MU0 * SIGMA))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    zf = np.linspace(0, T / 2, 400)
    Eex, _ = exact(f0, zf)
    norm = abs(Eex[0])
    ax1.plot(zf * 1e6, abs(Eex) / norm, color='#c03030', lw=3, label='exact')
    marker = {}
    for m in meshes:
        z, E, _ = solve(f0, MESHES[m])
        sel = z <= T / 2 + 1e-12
        ax1.plot(z[sel] * 1e6, abs(E[sel]) / norm, color=COLORS[m], lw=1.6, label=f'{method}, {LABELS[m]}', **marker)
    ax1.axvline(delta * 1e6, color='#c03030', lw=0.8, ls=':')
    ax1.text(delta * 1e6 + 0.02, 1.08, f'skin depth {delta * 1e6:.2f} um', fontsize=8, color='#c03030')
    ax1.set_xlabel('depth below the metal surface (um), centre of TopMetal2 at 1.5 um')
    ax1.set_ylabel('|E| = |J| / sigma, relative to the exact surface value')
    ax1.set_title(f'{method}: current density inside TopMetal2 (3 um) at {f0 / 1e9:.0f} GHz', fontsize=10)
    ax1.set_xlim(0, T / 2 * 1e6)
    ax1.set_ylim(-0.02, 1.2)
    ax1.legend(fontsize=8)
    # sheet resistance of the slab with both faces carrying current: Re(Zs) / 2 (DC: 1 / (sigma t))
    ax2.plot(fr / 1e9, ref / 2 * 1e3, color='#c03030', lw=3, label='exact')
    for m in meshes:
        ax2.plot(fr / 1e9, np.array([solve(f, MESHES[m])[2].real for f in fr]) / 2 * 1e3, color=COLORS[m], lw=1.8,
                 label=f'{method}, {LABELS[m]}')
    ax2.axhline(1e3 / (SIGMA * T), color='#888', lw=0.8, ls=':')
    ax2.text(98, 1e3 / (SIGMA * T) - 3.5, 'DC: 1 / (sigma t) = 11 mOhm', fontsize=8, color='#555555')
    ax2.set_xlim(0, 150)
    ax2.set_ylim(0, 80)
    ax2.set_xlabel('f (GHz)')
    ax2.set_ylabel('resistance per square of TopMetal2 (mOhm)')
    ax2.set_title(f'{method}: RF sheet resistance of TopMetal2 (3 um), current on both faces', fontsize=10)
    ax2.legend(fontsize=8, loc='upper left')
    fig.suptitle('1D model of the FEM order 2 scheme (not a Palace run); the metal faces are mesh lines',
                 fontsize=9, color='#555555')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'plots', filename), dpi=150)
    plt.close(fig)


LABELS = {'2 um': '2 um mesh', '1 um': '1 um mesh', '0.5 um': '0.5 um mesh'}

if __name__ == '__main__':
    fr = np.linspace(1e9, 150e9, 120)
    ref = np.array([exact(f, [0])[1].real for f in fr])
    figure('FEM order 2', fem_p2, ('2 um', '1 um', '0.5 um'), 'skin_1d_fem.png', fr, ref)
    fs = (1e9, 10e9, 20e9, 50e9, 100e9, 150e9)
    print('FEM order 2, loss / exact at ' + ', '.join(f'{f / 1e9:g}' for f in fs) + ' GHz')
    for m in MESHES:
        print(f'{m:12s}', ' '.join(f'{fem_p2(f, MESHES[m])[2].real / exact(f, [0])[1].real:6.3f}' for f in fs))
