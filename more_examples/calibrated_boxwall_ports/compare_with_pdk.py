"""Compare the calibrated Palace result of the rfcmim capacitor with the IHP SG13G2 PDK model.

Reads results/rfcmim_boxwall.s2p (raw: ports and 35 um feed lines included) and
results/rfcmim_boxwall_deembedded.s2p (calibrated, reference planes at the pcell edge), evaluates the PDK
subcircuit cap_rfcmim at the same frequencies and plots series capacitance and Q of all three.

The PDK model is the subcircuit cap_rfcmim from ihp-sg13g2/libs.tech/ngspice/models/capacitors_mod.lib
(IHP-Open-PDK, branch dev, commit 4bff57a), typical corner (cap_carea = 1.5e-15 from cornerCAP.lib),
written out here as a small circuit so that no circuit simulator is needed:

    PLUS --(Rskin || Lskin)-- Lmim -- Rmim -- Cmim --+-- Lfeed -- MINUS
                                                     |
                                                    Cox
                                                     |
                                              (Csub || Rsub)
                                                     |
                                                     bn (substrate = ground)

PLUS is the top plate (TopMetal1, port 1), MINUS the bottom plate (Metal5, port 2).

Usage:  python compare_with_pdk.py      (needs numpy, matplotlib, scikit-rf)
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import skrf as rf

HERE = os.path.dirname(os.path.abspath(__file__))

# pcell parameters of the capacitor in rfcmim_boxwall.gds: MIM 30 um along the feed (l) and 15 um across (w)
L_MIM = 30e-6
W_MIM = 15e-6
W_FEED = 10e-6


def pdk_rfcmim_y(f, l=L_MIM, w=W_MIM, wfeed=W_FEED, cap_carea=1.5e-15):
    """2-port Y-parameters of the PDK subcircuit cap_rfcmim, PLUS = port 1, MINUS = port 2, bn = ground.
    The parameter equations are those of capacitors_mod.lib, unchanged."""
    sf = 1e-6
    lplate = (0.353158 * (l / sf) + 0.485684 * l / w) * 1e-12
    lfeed = (6.03468 + 0.0814268 * (w / sf) - 0.821243 * np.log(wfeed / sf) / np.log(1.55)) * 1e-12
    lskin = 1.18545e-012 + 6.95462e-014 * (l / sf)
    cox = (0.48922 + 0.0965145 * (w + l) / sf + 0.00610947 * (w * l) / (sf * sf) + 0.017 * (wfeed / sf) * 5) * 1e-15
    csub = (50.1021 + 0.277881 * (w + l) / sf + 1.25023e-005 * (w * l) / (sf * sf)) * 1e-15
    rsub = 610.132 - 1.11685 * (w + l) / sf + 0.00434371 * (w * l) / (sf * sf)
    rmim = 0.0463973 + 0.00219577 * l / w + 0.961292 / (wfeed / sf) + 0.00307712 * (l / sf) + 0.000217076 * (l / sf) * l / w
    rskin = 0.154618 + 0.00702016 * (l / sf)
    lmim = max(lplate + lfeed - lskin, 1e-18)
    rsub = max(rsub, 10e-3)
    lfeed = max(lfeed, 1e-18)
    # cmim_core: ngspice semiconductor capacitor, C = CJ * l * w + 2 * CJSW * (l + w), with l and w in um (scale=1)
    cmim = cap_carea * (l / sf) * (w / sf) + 2 * 40e-18 * (l / sf + w / sf)
    cic = 1e-18   # Cic1, Cic2: tiny capacitors from PLUS and MINUS to bn

    jw = 2j * np.pi * np.asarray(f, dtype=float)
    z_skin = 1 / (1 / rskin + 1 / (jw * lskin))
    z_a = z_skin + jw * lmim + rmim + 1 / (jw * cmim)            # PLUS to the inner node 5
    z_b = jw * lfeed                                            # inner node 5 to MINUS
    y_sub = jw * csub + 1 / rsub
    y_sh = 1 / (1 / (jw * cox) + 1 / y_sub) + 1 / 1e9           # node 5 to bn: Cox in series with Csub||Rsub, Rdummy
    z_sh = 1 / y_sh
    Z = np.empty((len(jw), 2, 2), dtype=complex)                # T network
    Z[:, 0, 0] = z_a + z_sh
    Z[:, 1, 1] = z_b + z_sh
    Z[:, 0, 1] = Z[:, 1, 0] = z_sh
    Y = np.linalg.inv(Z)
    Y[:, 0, 0] += jw * cic
    Y[:, 1, 1] += jw * cic
    return Y, cmim


def series_c_and_q(f, Y):
    """series element between port 1 and port 2: Z = -1/Y21, C = -1/(omega Im Z), Q = -Im Z / Re Z"""
    z = -1 / Y[:, 1, 0]
    omega = 2 * np.pi * f
    return -1 / (omega * z.imag), -z.imag / z.real


def main():
    raw = rf.Network(os.path.join(HERE, 'results', 'rfcmim_boxwall.s2p'))
    cal = rf.Network(os.path.join(HERE, 'results', 'rfcmim_boxwall_deembedded.s2p'))

    curves = []
    for label, ntw, style in (('Palace, raw: ports and 35 µm feed lines included', raw, dict(color='0.6', ls='--')),
                              ('Palace, calibrated: capacitor alone', cal, dict(color='C0', lw=2))):
        keep = ntw.f > 0
        c, q = series_c_and_q(ntw.f[keep], ntw.y[keep])
        curves.append((label, ntw.f[keep], c, q, style))
    f = cal.f[cal.f > 0]
    y_pdk, cmim = pdk_rfcmim_y(f)
    c, q = series_c_and_q(f, y_pdk)
    curves.append(('PDK model cap_rfcmim (typical)', f, c, q, dict(color='C3', lw=2, ls=':')))

    # Q only from the lowest frequency of the calibration standards (fstop/20 = 9 GHz): below it, the loss of the
    # 35 um feed lines that the reference plane shift removes is extrapolated, see README.md
    f_q = 9e9
    fig, (ax_z, ax_c, ax_q) = plt.subplots(1, 3, figsize=(15, 4.4))
    for label, fx, c, q, style in curves:
        z = np.abs(1 / (2 * np.pi * fx * c))   # |Im Z| of the series element, from C = -1/(omega Im Z)
        ax_z.plot(fx / 1e9, z, label=label, **style)
        ax_c.plot(fx / 1e9, np.where(c > 0, c, np.nan) * 1e15, label=label, **style)
        sel = fx >= f_q * 0.999
        ax_q.plot(fx[sel] / 1e9, q[sel], label=label, **style)
    ax_z.set_yscale('log')
    ax_z.set_xlim(0, 180)
    ax_z.set_ylabel('series reactance |X| (ohm)')
    ax_z.set_title('series reactance: the dip is the self-resonance')
    ax_c.set_xlim(0, 40)
    ax_c.set_ylim(650, 1500)
    ax_c.set_ylabel('series capacitance (fF)')
    ax_c.set_title('series capacitance, below self-resonance')
    ax_q.set_xlim(0, 40)
    ax_q.set_ylim(0, 80)
    ax_q.set_ylabel('Q')
    ax_q.set_title('Q, from 9 GHz (lowest calibration frequency)')
    for ax in (ax_z, ax_c, ax_q):
        ax.set_xlabel('frequency (GHz)')
        ax.grid(True, alpha=0.3)
    ax_z.legend(fontsize=8, loc='upper right')
    fig.suptitle('rfcmim, MIM 30 µm x 15 µm, feed width 10 µm: series element from Y21')
    fig.tight_layout()
    out = os.path.join(HERE, 'results', 'rfcmim_vs_pdk.png')
    fig.savefig(out, dpi=120)
    print(f'saved {out}')

    print(f'PDK Cmim (area and perimeter) = {cmim * 1e15:.1f} fF')
    print('  f/GHz   ' + '   '.join(f'{"C/fF":>7} {"Q":>6}' for _ in curves) + '   (raw, calibrated, PDK)')
    for f0 in (1e9, 5e9, 10e9, 20e9, 40e9, 60e9, 100e9, 140e9, 180e9):
        row = []
        for _, fx, c, q, _ in curves:
            i = np.argmin(abs(fx - f0))
            row.append(f'{c[i] * 1e15:7.1f} {q[i]:6.1f}')
        i = np.argmin(abs(curves[1][1] - f0))
        print(f'  {curves[1][1][i] / 1e9:6.1f}   ' + '   '.join(row))


if __name__ == '__main__':
    main()
