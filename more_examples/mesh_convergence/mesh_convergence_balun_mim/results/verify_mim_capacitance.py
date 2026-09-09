#!/usr/bin/env python
"""Extract the MIM capacitor's simulated capacitance from the 1-port
verify_MIM_nominal_280 EM extraction and compare it to the nominal value
read from the GDS text label (280.026 fF).

Port 1 is a lumped via port bridging the capacitor's two plates directly
(Metal3 bottom-plate net to TopMetal2 top-plate net), so the 1-port
Y-parameter already represents the capacitor itself (plus any parasitic
series inductance/resistance of the port and connecting metal, which is
negligible at 1 GHz for a fF-range MIM cap): at 1 GHz, C = Im(Y11)/(2*pi*f).
"""
import os
import numpy as np
import skrf as rf

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_FILE = os.path.join(HERE, "snp", "verify_MIM_nominal_280.s1p")

NOMINAL_C_FF = 280.026


def main():
    if not os.path.isfile(SNP_FILE):
        print(f"Missing {SNP_FILE}, nothing to analyze yet.")
        return

    nw = rf.Network(SNP_FILE)
    freq = nw.frequency.f

    for i in range(len(freq)):
        f_hz = freq[i]
        Y11 = nw.y[i, 0, 0]
        C_F = Y11.imag / (2 * np.pi * f_hz)
        C_fF = C_F * 1e15
        S11 = nw.s[i, 0, 0]

        print(f"Frequency: {f_hz/1e9:.3f} GHz")
        print(f"S11: {S11.real:.6f} + {S11.imag:.6f}j  (|S11|={abs(S11):.4f}, arg={np.angle(S11, deg=True):.2f} deg)")
        print(f"Y11: {Y11.real:.6e} + {Y11.imag:.6e}j S")
        print(f"Simulated C: {C_fF:.3f} fF")
        print(f"Nominal C:   {NOMINAL_C_FF:.3f} fF")
        print(f"Difference:  {C_fF - NOMINAL_C_FF:+.3f} fF ({100*(C_fF-NOMINAL_C_FF)/NOMINAL_C_FF:+.2f}%)")
        print()


if __name__ == "__main__":
    main()
