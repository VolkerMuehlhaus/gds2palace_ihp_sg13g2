"""Independent reference: series impedance per unit length Z'(f) = R'(f) + j w L'(f) of a straight rectangular conductor
(width w, thickness t, conductivity sigma) at height h above an infinite PEC ground plane, by a 2D filament (PEEC) method.

Magneto-quasi-static, which is exact for the series impedance of a TEM / quasi-TEM line as long as the cross section is
much smaller than the wavelength (here: a few um against > 1 mm). The dielectric does not enter Z' (it only sets C').
The cross section is divided into rectangular filaments, graded towards all four surfaces (first cell much smaller than
the skin depth). Each filament k carries a uniform current I_k; all filaments see the same voltage drop V per unit length:

    sum_j ( R_k delta_kj + j w L_kj ) I_j = V,   sum_k I_k = 1   ->   Z' = V

with R_k = 1 / (sigma a_k b_k) and the loop inductance L_kj = mu0/(2 pi) * ln(d'_kj / d_kj), d'_kj the distance to the
image of filament j below the ground plane (image current -I_j). For k = j, d_kk is the geometric mean distance of the
rectangle (exact formula of Rosa/Grover); for close pairs, d_kj is the exact GMD between the two rectangles, evaluated
by Gauss quadrature.

Usage: python peec2d.py --selftest       (DC limit, grid convergence, comparison with the high-frequency surface limit)
"""
import sys
import numpy as np

MU0 = 4e-7 * np.pi


def graded(length, s0, smax, growth):
    """1D cell sizes over [0, length], s0 at both ends growing by `growth` up to smax in the middle"""
    left, s = [], s0
    while sum(left) + s < length / 2:
        left.append(s)
        s = min(s * growth, smax)
    rest = length - 2 * sum(left)
    nmid = max(1, int(np.ceil(rest / smax)))
    sizes = left + [rest / nmid] * nmid + left[::-1]
    return np.array(sizes)


def ln_gmd_rect(a, b):
    """ln of the geometric mean distance of a rectangle a x b from itself (Rosa & Grover)"""
    return (np.log(np.sqrt(a * a + b * b)) - (b * b / (12 * a * a)) * np.log(1 + a * a / (b * b))
            - (a * a / (12 * b * b)) * np.log(1 + b * b / (a * a))
            + (2 * b / (3 * a)) * np.arctan(a / b) + (2 * a / (3 * b)) * np.arctan(b / a) - 25.0 / 12.0)


def cross_section(w, t, h, s0=0.02, smax=0.25, growth=1.15):
    """filament centers (x, z), sizes (a, b); strip from x = -w/2..w/2, z = h..h+t (all in um)"""
    dx, dz = graded(w, s0, smax, growth), graded(t, s0, smax, growth)
    xe, ze = np.concatenate([[0], np.cumsum(dx)]) - w / 2, np.concatenate([[0], np.cumsum(dz)]) + h
    xc, zc = (xe[:-1] + xe[1:]) / 2, (ze[:-1] + ze[1:]) / 2
    X, Z = np.meshgrid(xc, zc, indexing='ij')
    A, B = np.meshgrid(dx, dz, indexing='ij')
    return X.ravel(), Z.ravel(), A.ravel(), B.ravel()


def ln_dist_matrix(X, Z, A, B, near=3.0, ng=6):
    """ln(GMD) between all filament pairs: exact self term, Gauss quadrature for near pairs, center distance otherwise"""
    n = len(X)
    D = np.hypot(X[:, None] - X[None, :], Z[:, None] - Z[None, :])
    np.fill_diagonal(D, 1.0)
    L = np.log(D)
    np.fill_diagonal(L, ln_gmd_rect(A, B))
    g, wg = np.polynomial.legendre.leggauss(ng)
    g, wg = g / 2, wg / 2                                       # on [-1/2, 1/2], weights sum to 1
    size = np.maximum(A, B)
    I, J = np.where((D < near * np.maximum(size[:, None], size[None, :])) & ~np.eye(n, dtype=bool))
    wts = wg[:, None, None, None] * wg[None, :, None, None] * wg[None, None, :, None] * wg[None, None, None, :]
    for s in range(0, len(I), 4000):
        i, j = I[s:s + 4000], J[s:s + 4000]
        xi = X[i, None] + A[i, None] * g[None, :]             # npair x ng (Gauss points across filament i)
        zi = Z[i, None] + B[i, None] * g[None, :]
        xj = X[j, None] + A[j, None] * g[None, :]
        zj = Z[j, None] + B[j, None] * g[None, :]
        dx = xi[:, :, None] - xj[:, None, :]                  # p, a (x of i), c (x of j)
        dz = zi[:, :, None] - zj[:, None, :]                  # p, b (z of i), d (z of j)
        r2 = dx[:, :, None, :, None] ** 2 + dz[:, None, :, None, :] ** 2         # p, a, b, c, d
        L[i, j] = 0.5 * np.einsum('pabcd,abcd->p', np.log(r2), wts)
    return L


class Strip:
    """precomputed geometry of one cross section; Z(f) per unit length in Ohm/m"""
    def __init__(self, w, t, h, sigma, **grid):
        X, Z, A, B = cross_section(w, t, h, **grid)
        self.n = len(X)
        um = 1e-6
        self.R = 1.0 / (sigma * A * B * um * um)                                     # Ohm/m per filament
        lnd = ln_dist_matrix(X, Z, A, B) + np.log(um)
        lnd_img = np.log(np.hypot(X[:, None] - X[None, :], Z[:, None] + Z[None, :]) * um)
        self.Lmat = MU0 / (2 * np.pi) * (lnd_img - lnd)                               # H/m
        self.w, self.t, self.h, self.sigma = w, t, h, sigma

    def Z(self, f):
        out = []
        ones = np.ones(self.n)
        for fk in np.atleast_1d(f):
            M = np.diag(self.R).astype(complex) + 2j * np.pi * fk * self.Lmat
            out.append(1.0 / np.sum(np.linalg.solve(M, ones)))
        return np.array(out)


def palace_zs(f, sigma, h):
    """Palace finite-thickness surface impedance (surfaceconductivityoperator.cpp): (gamma/sigma) coth(gamma h/2),
    h in um; h = 0 gives the half-space value (1 + j)/(sigma delta)"""
    w = 2 * np.pi * f
    delta = np.sqrt(2.0 / (MU0 * sigma * w))
    base = 1.0 / (sigma * delta)
    if h <= 0:
        return (1 + 1j) * base
    nu = h * 1e-6 / delta
    return base * ((np.sinh(nu) + np.sin(nu)) + 1j * (np.sinh(nu) - np.sin(nu))) / (np.cosh(nu) - np.cos(nu))


class Shell:
    """2D analogue of the gds2palace surface model: the conductor is a hollow shell, current flows only on its faces,
    each face with a surface impedance Zs (Ohm/sq). Faces are split into thin ribbons (graded towards the corners); ribbon
    k of width s_k has the series impedance Zs/s_k per unit length, and the ribbons couple through the same loop
    inductance as the filaments of Strip. zs(f, face) returns Zs for face 'top', 'bottom' or 'side'."""
    def __init__(self, w, t, h, zs, s0=0.01, smax=0.2, growth=1.15, tau=1e-3):
        xs, zsz = graded(w, s0, smax, growth), graded(t, s0, smax, growth)
        xc = np.cumsum(xs) - xs / 2 - w / 2
        zc = np.cumsum(zsz) - zsz / 2 + h
        X = np.concatenate([xc, xc, np.full(len(zc), -w / 2 + tau / 2), np.full(len(zc), w / 2 - tau / 2)])
        Z = np.concatenate([np.full(len(xc), h + t - tau / 2), np.full(len(xc), h + tau / 2), zc, zc])
        A = np.concatenate([xs, xs, np.full(len(zc), tau), np.full(len(zc), tau)])
        B = np.concatenate([np.full(len(xc), tau), np.full(len(xc), tau), zsz, zsz])
        self.face = np.array(['top'] * len(xc) + ['bottom'] * len(xc) + ['side'] * (2 * len(zc)))
        self.width = np.concatenate([xs, xs, zsz, zsz]) * 1e-6                       # m
        um = 1e-6
        lnd = ln_dist_matrix(X, Z, A, B) + np.log(um)
        lnd_img = np.log(np.hypot(X[:, None] - X[None, :], Z[:, None] + Z[None, :]) * um)
        self.Lmat = MU0 / (2 * np.pi) * (lnd_img - lnd)
        self.zs, self.n = zs, len(X)

    def Z(self, f):
        out, ones = [], np.ones(self.n)
        for fk in np.atleast_1d(f):
            zr = np.array([self.zs(fk, fc) for fc in ('top', 'bottom', 'side')])
            zk = np.where(self.face == 'top', zr[0], np.where(self.face == 'bottom', zr[1], zr[2])) / self.width
            M = np.diag(zk) + 2j * np.pi * fk * self.Lmat
            out.append(1.0 / np.sum(np.linalg.solve(M, ones)))
        return np.array(out)


def selftest():
    sigma, t, h = 30.3e6, 3.0, 11.0
    print('DC limit and grid convergence (w = 4.5 um, t = 3 um, h = 11 um):')
    for grid in (dict(s0=0.08, smax=0.5), dict(s0=0.04, smax=0.35), dict(s0=0.02, smax=0.25), dict(s0=0.01, smax=0.18)):
        s = Strip(4.5, t, h, sigma, **grid)
        z = s.Z([1e6, 10e9, 50e9, 150e9])
        print(f"  s0 {grid['s0']:5.2f} um, smax {grid['smax']:4.2f} um, {s.n:5d} filaments: R' = "
              + ', '.join(f'{x.real:8.2f}' for x in z) + ' Ohm/m at 1 MHz, 10, 50, 150 GHz;'
              + f"  L'(1 MHz) {z[0].imag / (2 * np.pi * 1e6) * 1e9:.2f} nH/m")
    print(f'  analytic DC: 1/(sigma w t) = {1 / (sigma * 4.5e-6 * 3e-6):.2f} Ohm/m')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
