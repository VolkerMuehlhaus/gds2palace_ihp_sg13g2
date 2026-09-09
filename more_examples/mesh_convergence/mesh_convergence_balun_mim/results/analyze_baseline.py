#!/usr/bin/env python
"""Baseline (nominal mesh, no sweep yet) S-parameter analysis for
trans_100diff_to_80se_ports: a 3-port structure with port 1 single-ended
(true external system impedance 80 ohm) and ports 2/3 a differential pair
(true external differential impedance 100 ohm). All 3 ports were simulated
at port_Z0=50.0 -- this script re-references the result to the true mixed
single-ended/differential system impedances.

The 3-port Z-matrix is reduced to a 2-port single-ended/differential-mode
equivalent (port a = SE port 1, port b = differential mode of ports 2/3)
using the same plain "engineering" differential-impedance convention
already validated in the balun2x1 and transformer studies (Zdiff = Vdiff/I
with I the current in one leg, NOT the Bockelman-Eisenstadt power-
normalized Idm=(I2-I3)/sqrt(2) convention -- using B&E's own Zbb would be
exactly half this Zbb, so referencing it against Z02 here would silently
impose a 2*Z02 differential termination instead of Z02):

    Zaa = Z11
    Zab = Z12 - Z13
    Zba = Z21 - Z31
    Zbb = Z22 - Z23 - Z32 + Z33

Derivation: drive the pair with I2=-I3=I (pure differential, no common
current) and I1 driven independently; then V1 = Z11*I1 + (Z12-Z13)*I and
Vdiff = V2-V3 = (Z21-Z31)*I1 + (Z22-Z23-Z32+Z33)*I, which reads off Zaa,
Zab, Zba, Zbb directly (no extra factors) with Ia=I1, Ib=I. This also
drops the common-mode row/column of the full 3-mode (SE, DM, CM) transform,
exact under the standard S-parameter assumption that a port not included
in the matrix is terminated in its own reference impedance.

The resulting 2-port is then converted to S-parameters at the real,
unequal reference impedances Z01=80 ohm (SE) / Z02=100 ohm (differential)
using the general unequal-reference-impedance 2-port Z->S formula (same
one used in the balun2x1 and transformer studies):

    D      = (Zaa+Z01)*(Zbb+Z02) - Zab*Zba
    Sss11  = ((Zaa-Z01)*(Zbb+Z02) - Zab*Zba) / D
    Sdd22  = ((Zaa+Z01)*(Zbb-Z02) - Zab*Zba) / D
    Sds21  = 2*Zba*sqrt(Z01*Z02) / D   (differential output from SE input)

Reads the raw (non-de-embedded) 3-port Touchstone from results/snp/ -- the
mesh convergence sweep uses raw S-parameters throughout, so this baseline
uses the same convention for consistency -- and writes an S-parameter
table (band edges + center) and mag/phase plots for Sss11, Sdd22, Sds21.
"""
import os
import csv
import numpy as np
import skrf as rf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SNP_DIR = os.path.join(HERE, "snp")
PLOT_DIR = os.path.join(HERE, "plots")
SNP_FILE = os.path.join(SNP_DIR, "trans_100diff_to_80se_ports.s3p")

Z01 = 80.0   # true single-ended external system impedance (port 1)
Z02 = 100.0  # true differential external system impedance (ports 2/3)

EVAL_FREQS_GHZ = [17, 19.5, 22]  # band edges + center


def db(x):
    return 20 * np.log10(np.abs(x))


def deg(x):
    return np.angle(x, deg=True)


def mixed_mode_traces(nw, z01=Z01, z02=Z02):
    Z = nw.z
    Zaa = Z[:, 0, 0]
    Zab = Z[:, 0, 1] - Z[:, 0, 2]
    Zba = Z[:, 1, 0] - Z[:, 2, 0]
    Zbb = Z[:, 1, 1] - Z[:, 1, 2] - Z[:, 2, 1] + Z[:, 2, 2]
    D = (Zaa + z01) * (Zbb + z02) - Zab * Zba
    Sss11 = ((Zaa - z01) * (Zbb + z02) - Zab * Zba) / D
    Sdd22 = ((Zaa + z01) * (Zbb - z02) - Zab * Zba) / D
    Sds21 = 2 * Zba * np.sqrt(z01 * z02) / D
    return {"Sss11": Sss11, "Sds21": Sds21, "Sdd22": Sdd22}


def value_at_freq(freq, x, freq_hz):
    i = int(np.argmin(np.abs(freq - freq_hz)))
    return x[i] if abs(freq[i] - freq_hz) < 0.6e9 else None


def main():
    if not os.path.isfile(SNP_FILE):
        print(f"Missing {SNP_FILE}, nothing to analyze yet.")
        return

    nw = rf.Network(SNP_FILE)
    nw.name = "nominal (refined_cellsize=3um, Metal3=5um)"
    freq = nw.frequency.f
    traces = mixed_mode_traces(nw)

    os.makedirs(PLOT_DIR, exist_ok=True)

    csv_path = os.path.join(HERE, "s_parameter_table.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Param"] + [f"{fg} GHz |S| (dB)" for fg in EVAL_FREQS_GHZ] +
                         [f"{fg} GHz arg(S) (deg)" for fg in EVAL_FREQS_GHZ])
        for pname, x in traces.items():
            mags = [value_at_freq(freq, x, fg * 1e9) for fg in EVAL_FREQS_GHZ]
            row = [pname]
            row += [f"{db(v):.3f}" if v is not None else "n/a" for v in mags]
            row += [f"{deg(v):.2f}" if v is not None else "n/a" for v in mags]
            writer.writerow(row)
    print(f"Wrote S-parameter table: {csv_path}")

    colors = {"Sss11": "#4c72b0", "Sds21": "#55a868", "Sdd22": "#c44e52"}
    for pname, x in traces.items():
        fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        freq_ghz = freq / 1e9
        ax_mag.plot(freq_ghz, db(x), color=colors[pname])
        ax_mag.set_ylabel(f"|{pname}| (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.set_title(f"{pname} at true system impedance (Z01={Z01:.0f} ohm SE, Z02={Z02:.0f} ohm diff)")
        ax_phase.plot(freq_ghz, deg(x), color=colors[pname])
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel(f"arg({pname}) (deg)")
        ax_phase.grid(True, alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(PLOT_DIR, f"{pname.lower()}_baseline.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Wrote plot: {out_path}")


if __name__ == "__main__":
    main()
