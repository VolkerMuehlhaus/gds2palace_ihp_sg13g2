########################################################################
#
# Copyright 2025 Volker Muehlhaus and IHP PDK Authors
#
# Licensed under the GNU General Public License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.gnu.org/licenses/gpl-3.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################

# convert Palace output port-S.csv to Touchstone format, 
# walk through directory and combine all excitation

# new version for new Palace output that creates multi excitations in one common output file
# updated 19-Oct-2025 Mue: support more than 9 ports
# updated 08-Nov-2025 Mue: added evaluation for optional port impedance file port_information.json that is created by new gds2palace code
# updated 13-Nov-2025 Mue: added simple de-embedding of parasitic port inductance (flat ribbon calculation)
# updated 26-Nov-2025 Mue: also read Elmer FEM files
# updated 22-Sep-2026 Mue: handle an interrupted Palace run (e.g. killed by setupEM's
#   memory limit, or OOM-killed) - a blank/truncated trailing CSV line, or Palace's own
#   "NULL" placeholder for an unsolved excitation, no longer crashes with an IndexError
#   or gets silently written into the Touchstone file; affected S-parameters are set to
#   0.0 dB / 0 deg and flagged both on stdout and in a comment line in the output file
# updated 12-Oct-2026 Mue: port de-embedding cascaded all negative port inductances at port 1
#   (none at the other ports); each port now gets its own value, in port number order
#   (bug found by Gianluca Simone and David Lurz, FAU)
# updated 08-Nov-2026: calibrated de-embedding of ports at port walls (box sides set to 'PORTWALL'), from the
#   calibration standards that gds2palace writes and run_sim solves; Touchstone comment line per port with the
#   method used, sidecar <name>_deembedding.json; the standards' own results are skipped here
# updated 12-Nov-2026: --help and --version (before, any option was ignored and the conversion ran), optional
#   folder argument instead of the current folder, exit code 2 for a folder that does not exist

import os, re, sys, json, math
import skrf as rf
from   skrf.circuit import Circuit
import numpy as np


def todb(x):
    return 20 * np.log10(np.abs(x))

def toangle(x):
    return -np.degrees(np.angle(x))


def parse_elmer_results(found_filename, freq, S_dB, S_arg):
    freq_unit = 'GHz'

    names_filename = found_filename
    data_filename  = names_filename.replace('.names','')

    # Parse column names
    column_names = []
    with open(names_filename, 'r') as namesfile:
        for line in namesfile:
            if ':' in line and line.strip()[0].isdigit():
                parts = line.split(':')
                if len(parts) >= 3:
                    name = parts[2].strip()
                    column_names.append(name)

    cmf_names = [name for name in column_names if name.startswith("cmf")]
    count_cmf = len(cmf_names)
    num_ports = int(math.sqrt(count_cmf/2))

    # find column with frequency
    omega_column = column_names.index('angular frequency')
    
    # find column with re{S11}
    if 'cmf 11' in column_names:
        re_s11_column = column_names.index('cmf 11')
    else:
        re_s11_column = column_names.index('cmf 1 1')


    # find column with im{S11}
    if 'cmf im 11' in column_names:
        im_s11_column = column_names.index('cmf im 11')
    else:
        im_s11_column = column_names.index('cmf im 1 1')


    if re_s11_column+num_ports**2 != im_s11_column:
        print('Incorrect number of values in data file, does not match port count') 
        exit(1)


    # read data file
    data = np.loadtxt(data_filename)

    if data.ndim==2:
        # we have multiple frequencies
        omegalist = data[:, omega_column]
    else:
        # we have only one freqiency point
        omegalist = [data[omega_column]]
    for omega in omegalist:
        freq.append(omega / (1e9*2*math.pi))


    # -------------------------
    # Build S-matrices
    # -------------------------

    # loop over frequencies
    numfreq = len(omegalist)
    for f_index in range(numfreq):
        dB = {}
        arg = {}
        for m in range(num_ports):
            for n in range(num_ports):
                key = str(m+1) + ' ' + str(n+1)
                data_offset = m*num_ports + n
                if data.ndim==2:
                    # more than 1 frequency point
                    real_part = data[f_index, re_s11_column + data_offset]
                    imag_part = data[f_index, im_s11_column + data_offset]
                else:
                    # single frequency data    
                    real_part = data[re_s11_column + data_offset]
                    imag_part = data[im_s11_column + data_offset]

                Smn = real_part + 1j * imag_part
                dB[key] = todb(Smn)
                arg[key] = toangle(Smn)

        S_dB.append(dB)
        S_arg.append(arg)

    # set unit GHz
    freq_unit = 'GHz'

    return num_ports, freq_unit      


def parse_palace_csv (input_filename, freq, S_dB, S_arg):
    params = []

    with open(input_filename) as input_file:
        for line in input_file:
            aline = line.rstrip()
            aline = aline.replace(",","")
            aline = aline.replace("(dB)","")
            aline = aline.replace("(deg.)","")

            dB = {}
            arg = {}

            # check if we have the header line
            if 'Hz)' in aline:
                # get unit from header line
                items = aline.split()
                freq_unit = re.sub('[()]', '', items[1])

                # find what parameters we have in this line
                # items are like this:      |S[1][1]| arg(S[1][1])

                num_ports = 0

                for item in items:
                    if '|' in item:
                        Sxx = item.replace('|S', '')
                        Sxx = Sxx.replace('|', '')
                        # Sxx is like this: [1][1]'
                        Sxx = Sxx.replace('][', ' ')
                        # Sxx is like this: [1 1]
                        Sxx = Sxx.replace('[', '')
                        Sxx = Sxx.replace(']', '')
                        # Sxx is like this: 1 1
                        params.append(str(Sxx))

                        # get port indices a and b from Sxx
                        splitted = Sxx.split()
                        a = int(splitted [0])
                        b = int(splitted [1])
                        num_ports = max(num_ports,a,b)

                print('Number of ports: ', num_ports)

            else:
                aline = aline.strip()
                if not aline:
                    # blank/truncated trailing line, e.g. the solver run was
                    # interrupted (OOM-killed) mid-write and never finished it
                    continue

                # process data line
                items = aline.split()
                f = items[0]
                for param in params:
                    dB_index = 2*params.index(param) + 1
                    arg_index = dB_index+1

                    # an interrupted solver run can leave a data line that is
                    # missing trailing columns entirely (not even a "NULL"
                    # placeholder) - treat those the same as Palace's own
                    # "NULL" for a value it had not computed yet, rather than
                    # raising an IndexError here
                    dB_value  = items[dB_index]  if dB_index  < len(items) else 'NULL'
                    arg_value = items[arg_index] if arg_index < len(items) else 'NULL'

                    dB[param] = dB_value
                    arg[param] = arg_value

                    # do we already have the frequency point?
                    if f in freq:
                        f_index = freq.index(f)
                        dB_dict = S_dB[f_index]
                        arg_dict = S_arg[f_index]

                        dB_dict[param] = dB_value
                        arg_dict[param] = arg_value

                    else:
                        freq.append(f)
                        S_dB.append(dB)
                        S_arg.append(arg)

    input_file.close()  
    return num_ports, freq_unit      

# ---------------------------

def traverse_directories(path, level=0):
    try:
        items_in_path = os.listdir(path)
        for item in items_in_path:
            item_path = os.path.join(path, item)

            if os.path.isdir(item_path):
                traverse_directories(item_path, level + 1)
            elif item=='port-S.csv':
                found_datafiles.append(item_path)
            elif item=='scalar_results.names':
                found_datafiles.append(item_path)

    except PermissionError:
        print(item +  "[Permission Denied]")
    except FileNotFoundError:
        print(item +  "[Not Found]")

# ----------------------

# extrapolate down to DC 

def extrapolate_to_DC (snp_filename):
    nw = rf.Network(snp_filename)

    returnval = ''
    # check if we have point below 1 GHz, otherwise exit
    if nw.frequency.npoints > 20:
        if nw.frequency.start <= 1e9:
            if True: # nw.frequency.npoints > 50:
                # extrapolate to DC
                extrapolated = nw.extrapolate_to_dc(points=None, dc_sparam=None,  kind='cubic', coords='polar')
                filename, file_extension = os.path.splitext(snp_filename)
                # keep the original .sNp extension explicitly, rather than relying on
                # write_touchstone() to re-append it - it only does that when its own
                # get_extn() finds no dot at all in the name, and a model name containing
                # a literal '.' (e.g. a dimension "do82.41" or temperature "T125.0C")
                # makes it mistake that trailing fragment for an existing extension,
                # silently writing the file with no extension at all
                out_filename = filename + '_dc' + file_extension
                extrapolated.write_touchstone(out_filename, skrf_comment='DC point added by extrapolation', form='db', write_noise=True)
                returnval = out_filename
                print('Created file with DC extrapolation: ', out_filename,'\n')
            else:
                print('Not enough frequency points, skipping DC extrapolation')    
        else:
            print('No data at low frequency, skipping DC extrapolation')    
    else:
        print('Skipping DC extrapolation, not enough frequency points')    
    # return empty string or filename of DC extrapolated data
    return returnval

# ----------------------

# optional de-embdedding of port inductance 

def flat_strip_inductance(length, width, thickness, unit):
    """
       Flat Wire Inductor Calculator
       The original for this equation is by F.E. Terman and can be found in the Radio Engineers Handbook, McGraw-Hill, New York, 1945.
    """
    return 2e-7* length * unit * (math.log(2*length/(width+thickness)) + 0.5 + 0.2235*(width+thickness)/length)



def port_deembedding (snp_filename, port_info_available, port_info_data):
    if port_info_available:
        print('Port de-embedding based on port geometry data')
        unit = port_info_data.get("unit", 1e-6) # default dimension is micron 

        # calculate parasitic port inductance for all ports
        Lport = {}
        portlist = port_info_data["ports"]
        for port in portlist:
            portnum = port.get("portnumber", None)    
            length  = port.get("length", None)
            width   = port.get("width", None)
            if (length is not None) and (width is not None) and (portnum is not None):
                thickness = 0 # Palace ports are 2D sheets with no thickness
                L = flat_strip_inductance(length, width, thickness, unit)
                # store into dict for this port number, just in case the port numbers in the file are in wrong sorting order;
                # a multielement port has one entry per element: the elements are in parallel, so are their inductances
                if str(portnum) in Lport:
                    L = 1.0 / (1.0 / Lport[str(portnum)] + 1.0 / L)
                Lport[str(portnum)]=L

        # load SnP data and apply negative series L at each port
        ntwk  = rf.Network(snp_filename)
        freq = ntwk.frequency
        N = ntwk.nports

        # Create a Media object (needed for Media.inductor)
        media = rf.media.DefinedGammaZ0(frequency=freq, z0=50)

        # Build the de-embedding circuit with explicit, named connections:
        # external port n -- series L of port n -- DUT port n
        # Chaining skrf connect() instead renumbers the remaining ports on every call, which is easy
        # to get wrong (it put all L values at port 1 before). The L values are looked up by port
        # number, a port without geometry data is connected directly (L = 0).
        dut = ntwk.copy()
        dut.name = 'dut'
        connections = []
        for n in range(N):
            if str(n+1) in Lport:
                L = -Lport[str(n+1)]
                print(f'Cascading L= {L*1e12:.2f} pH at port {n+1}')
            else:
                L = 0.0
                print(f'No geometry data for port {n+1}, port not de-embedded')
            inductor = media.inductor(L=L, name=f'L{n+1}')
            port = Circuit.Port(freq, name=f'P{n+1}', z0=dut.z0[:, n])
            connections += [[(port, 0), (inductor, 0)], [(inductor, 1), (dut, n)]]
        ntwk = Circuit(connections).network

        filename, file_extension = os.path.splitext(snp_filename)
        # keep the original .sNp extension explicitly - see the matching comment in
        # extrapolate_to_DC() for why relying on write_touchstone()'s own extension
        # auto-detection is unsafe here
        out_filename = filename + '_deembedded' + file_extension
        ntwk.write_touchstone(out_filename, skrf_comment='De-embedded by adding negative series L at ports', form='db', write_noise=True)
        print('Created file with de-embedding (cascaded negative port L): ', out_filename,'\n')
    else:
        print('Skipping port de-embedding, not port geometry information available')    



# ----------------------

# calibrated de-embedding of ports at port walls (box sides set to 'PORTWALL' in gds2palace)
#
# gds2palace writes two standards per port wall, thru lines of length L and 2 L with the cross-section at the wall, and
# lists them in port_information.json ("port_walls"). The port is removed by double delay (Rautio): the cascade
# T_L^-1 T_2L T_L^-1 leaves the port twice, which gives its shunt and series elements. The maths is copied from
# test_data/port_deembedding_study/soc_deembed.py, where it is tested with ideal circuits; numpy only. All matrices are
# block matrices over the N ports of one wall, so the coupling between them is removed too. The error network is
# removed in the S domain, not through Y, which is singular for a DC-extrapolated inductor.

C0 = 299792458.0


def _blocks(M):
    N = M.shape[-1] // 2
    return M[..., :N, :N], M[..., :N, N:], M[..., N:, :N], M[..., N:, N:]


def _join(a, b, c, d):
    return np.concatenate((np.concatenate((a, b), axis=-1), np.concatenate((c, d), axis=-1)), axis=-2)


def s2t(S, z0=50.0):
    """2N-port S (one real reference impedance) to the cascade matrix, [V1; I1] = T [V2; -I2], currents into the ports"""
    s11, s12, s21, s22 = _blocks(S)
    N = s11.shape[-1]
    I = np.broadcast_to(np.eye(N, dtype=complex), s11.shape)
    si = np.linalg.inv(s21)
    W = _join(-si @ s22, si, s12 - s11 @ si @ s22, s11 @ si)
    q = np.sqrt(z0)
    Q1 = _join(q * I, q * I, I / q, -I / q)
    Q2i = 0.5 * _join(I / q, -q * I, I / q, q * I)
    return Q1 @ W @ Q2i


def t2s(T, z0=50.0):
    """the inverse of s2t()"""
    N = T.shape[-1] // 2
    I = np.broadcast_to(np.eye(N, dtype=complex), T.shape[:-2] + (N, N))
    q = np.sqrt(z0)
    Q1i = 0.5 * _join(I / q, q * I, I / q, -q * I)
    Q2 = _join(q * I, q * I, -I / q, I / q)
    w11, w12, w21, w22 = _blocks(Q1i @ T @ Q2)
    s21 = np.linalg.inv(w12)
    s22 = -s21 @ w11
    s11 = w22 @ s21
    s12 = w21 - s11 @ w11
    return _join(s11, s12, s21, s22)


def rev_t(T):
    """the same reciprocal network seen from the other side"""
    a, b, c, d = _blocks(T)
    tr = lambda m: m.swapaxes(-1, -2)
    return _join(tr(d), tr(b), tr(c), tr(a))


def shunt_t(Y):
    N = Y.shape[-1]
    I = np.broadcast_to(np.eye(N, dtype=complex), Y.shape)
    return _join(I, np.zeros_like(Y), Y, I)


def series_t(Z):
    N = Z.shape[-1]
    I = np.broadcast_to(np.eye(N, dtype=complex), Z.shape)
    return _join(I, Z, np.zeros_like(Z), I)


def port_from_double(Dbl, iterations=20):
    """two element port (shunt Y outside, series Zs inside) from T_L^-1 T_2L T_L^-1; returns Y, Zs"""
    M = np.linalg.inv(Dbl)
    _, m12, m21, _ = _blocks(M)
    Zs = m12 / 2
    Ys = m21 / 2
    for _ in range(iterations):
        Ys = m21 / 2 - Ys @ Zs @ Ys
    return Ys, Zs


def _eig_fun(T, fun):
    """matrix function through the eigen decomposition, per frequency"""
    w, V = np.linalg.eig(T)
    return V @ (fun(w)[..., None] * np.linalg.inv(V))


def deembed_s(Sm, Se):
    """remove an error network from a measured N-port. Se: 2N-port S of the error network, external ports first. From
    Sm = S11 + S12 G (1 - S22 G)^-1 S21:  X = S12^-1 (Sm - S11) S21^-1,  G = (1 + X S22)^-1 X"""
    s11, s12, s21, s22 = _blocks(Se)
    X = np.linalg.solve(s12, Sm - s11) @ np.linalg.inv(s21)
    I = np.broadcast_to(np.eye(Sm.shape[-1], dtype=complex), Sm.shape)
    return np.linalg.solve(I + X @ s22, X)


def _interp_per_omega(f_std, X_std, f):
    """an element known at the standards' frequencies, at the frequencies f: the imaginary part per omega (inductance,
    capacitance) and the real part per sqrt(f) (conductor loss, which follows the surface impedance) are interpolated
    linearly in f and held constant outside the standards' range"""
    im = X_std.imag / (2 * np.pi * f_std)[:, None, None]
    re = X_std.real / np.sqrt(f_std)[:, None, None]
    out = np.empty((len(f),) + X_std.shape[1:], dtype=complex)
    for a in range(X_std.shape[1]):
        for b in range(X_std.shape[2]):
            out[:, a, b] = np.interp(f, f_std, re[:, a, b]) * np.sqrt(f) + 1j * np.interp(f, f_std, im[:, a, b]) * 2 * np.pi * f
    return out


def read_palace_s(csv_filename):
    """frequencies (Hz) and complex S [nf, n, n] of a Palace port-S.csv"""
    freq, S_dB, S_arg = [], [], []
    num_ports, freq_unit = parse_palace_csv(csv_filename, freq, S_dB, S_arg)
    scale = {'HZ': 1.0, 'KHZ': 1e3, 'MHZ': 1e6, 'GHZ': 1e9}[freq_unit.upper()]
    f = np.array([float(x) for x in freq]) * scale
    S = np.zeros((len(f), num_ports, num_ports), dtype=complex)
    for k in range(len(f)):
        for i in range(num_ports):
            for j in range(num_ports):
                key = f'{i + 1} {j + 1}'
                dB, arg = S_dB[k].get(key, 'NULL'), S_arg[k].get(key, 'NULL')
                if dB == 'NULL' or arg == 'NULL':
                    raise ValueError(f'{csv_filename}: S{i + 1}{j + 1} missing at {freq[k]} {freq_unit}')
                S[k, i, j] = 10 ** (float(dB) / 20) * np.exp(1j * np.radians(float(arg)))
    order = np.argsort(f)
    return f[order], S[order]


def _line_report(T_line, length, f, unit):
    """per mode: Z0 (circuit theory, per line), n_eff and loss in dB/mm of the calibrated line section. One line: one mode;
    a symmetric pair: common (index 0) and differential (index 1); more lines: n_eff and loss from the eigenvalues"""
    a, b, c, d = _blocks(T_line)
    N = a.shape[-1]
    w = 2 * np.pi * f
    out = []
    if N <= 2:
        if N == 1:
            modes = [('single', lambda m: m[..., 0, 0])]
        else:
            modes = [('common', lambda m: (m[..., 0, 0] + m[..., 0, 1] + m[..., 1, 0] + m[..., 1, 1]) / 2),
                     ('differential', lambda m: (m[..., 0, 0] - m[..., 0, 1] - m[..., 1, 0] + m[..., 1, 1]) / 2)]
        for name, mode in modes:
            ma, mb, mc, md = mode(a), mode(b), mode(c), mode(d)
            x = np.arccosh((ma + md) / 2)
            x = np.where(x.imag < 0, -x, x)
            gamma = x / (length * unit)
            z = np.sqrt(mb / mc)
            z = np.where(z.real < 0, -z, z)
            out.append({'mode': name, 'Z0': z, 'n_eff': gamma.imag * C0 / w, 'loss_dB_per_mm': 8.686 * gamma.real / 1000})
    else:
        # eigenvalues of T are exp(+-gamma L): keep the N forward waves (positive phase), sorted by n_eff
        g = np.log(np.linalg.eigvals(T_line)) / (length * unit)
        g = np.where(g.imag < 0, -g, g)
        g = np.take_along_axis(g, np.argsort(g.imag, axis=-1), axis=-1)[:, ::2][:, :N]
        for k in range(g.shape[-1]):
            out.append({'mode': f'mode {k + 1}', 'Z0': None, 'n_eff': g[:, k].imag * C0 / w,
                        'loss_dB_per_mm': 8.686 * g[:, k].real / 1000})
    return out


def _calibrate_group(group, sim_path, unit):
    """port elements and line of one port wall from its two standards; returns a dict with the standards' frequencies,
    the shunt Y and series Zs of the port, the line's A = log(T_line) / L, and the diagnostics"""
    f1, S1 = read_palace_s(os.path.join(sim_path, group['standards'][0]['output'], 'port-S.csv'))
    f2, S2 = read_palace_s(os.path.join(sim_path, group['standards'][1]['output'], 'port-S.csv'))
    if len(f1) != len(f2) or np.max(np.abs(f1 - f2)) > 1e-3 * np.max(f1):
        raise ValueError(f"port wall {group['side']}: the two standards were solved at different frequencies")
    sym = lambda S: (S + S.swapaxes(-1, -2)) / 2            # the reciprocal part
    TL, T2L = s2t(sym(S1)), s2t(sym(S2))
    TLi = np.linalg.inv(TL)
    Ys, Zs = port_from_double(TLi @ T2L @ TLi)
    P = shunt_t(Ys) @ series_t(Zs)
    L = group['L']
    T_line = np.linalg.inv(P) @ TL @ np.linalg.inv(rev_t(P))
    A = _eig_fun(T_line, np.log) / L
    w = 2 * np.pi * f1
    n = Ys.shape[-1]
    report = _line_report(T_line, L, f1, unit)
    doubtful = []
    C = Ys.imag / w[:, None, None]
    Ls = Zs.imag / w[:, None, None]
    for k in range(n):
        port = group['ports'][k]
        if np.any(C[:, k, k] < 0):
            doubtful.append(f'port {port}: negative port capacitance')
        if np.any(Ys.real[:, k, k] > Ys.imag[:, k, k]):
            doubtful.append(f'port {port}: the port loses more than it stores (the standards radiate, or the ground is far)')
        if np.any(np.abs(w * Ls[:, k, k]) > 0.1 / np.maximum(np.abs(w * C[:, k, k]), 1e-30)):
            doubtful.append(f'port {port}: large series part, the port is not the small shunt element the method assumes')
    n_max = math.sqrt(group.get('eps_max', 1e9)) * 1.05
    for m in report:
        if np.any(m['n_eff'] < 0.95) or np.any(m['n_eff'] > n_max):
            doubtful.append(f"{m['mode']} mode: n_eff {np.min(m['n_eff']):.3g} to {np.max(m['n_eff']):.3g} outside 1 to "
                            f"sqrt(eps_max) = {n_max / 1.05:.3g}")
    n_top = max(float(m['n_eff'][-1]) for m in report)
    valid = min(f1[-1], C0 / (n_top * 5 * L * unit)) if n_top > 0 else f1[-1]
    return {'f': f1, 'Ys': Ys, 'Zs': Zs, 'A': A, 'report': report, 'doubtful': doubtful, 'valid_to_GHz': valid / 1e9}


def _error_network(f, N, port_info, groups_cal, unit):
    """2N-port S at 50 ohm of all port parasitics: calibrated blocks for the port walls (with the optional reference
    plane shift), the estimated port inductance for the other ports with geometry data, a plain connection otherwise.
    Returns the S-matrix and one description line per port."""
    Se = np.zeros((len(f), 2 * N, 2 * N), dtype=complex)
    idx = np.arange(N)
    Se[:, idx, N + idx] = 1
    Se[:, N + idx, idx] = 1
    method = {}
    unit_name = 'um' if abs(unit - 1e-6) < 1e-12 else f'x {unit:g} m'
    for group, cal in groups_cal:
        n = len(group['ports'])
        Ys = _interp_per_omega(cal['f'], cal['Ys'], f)
        Zs = _interp_per_omega(cal['f'], cal['Zs'], f)
        E = shunt_t(Ys) @ series_t(Zs)
        # the reference plane from the port wall: the user's shift from the layout edge, plus the extension that moved
        # the port wall outward
        extension = float(group.get('extension', 0.0))
        user_shift = float(group.get('shift', 0.0))
        shift = user_shift + extension
        if shift:
            A = _interp_per_omega(cal['f'], cal['A'], f)
            E = E @ _eig_fun(A * shift, np.exp)
        e = t2s(E)
        ports = [p - 1 for p in group['ports']]
        for i, pi in enumerate(ports):
            for j, pj in enumerate(ports):
                Se[:, pi, pj] = e[:, i, j]
                Se[:, pi, N + pj] = e[:, i, n + j]
                Se[:, N + pi, pj] = e[:, n + i, j]
                Se[:, N + pi, N + pj] = e[:, n + i, n + j]
        if extension:
            where = (('at the layout edge' if not user_shift else f'{user_shift:g} {unit_name} into the layout')
                     + f' (port wall moved {extension:g} {unit_name} outward, feed extended)')
        else:
            where = ('at the wall' if not shift else f'{shift:g} {unit_name} into the layout' if shift > 0
                     else f'{-shift:g} {unit_name} outside the wall')
        for p in group['ports']:
            method[p] = f"calibrated at port wall {group['side']}, reference plane {where}"
    estimated = {}
    for port in port_info.get('ports', []):
        p = port.get('portnumber')
        if p is None or p in method or p > N or port.get('length') is None or port.get('width') is None:
            continue
        L = flat_strip_inductance(port['length'], port['width'], 0, unit)
        # the elements of a multielement port are in parallel
        estimated[p] = L if p not in estimated else 1.0 / (1.0 / estimated[p] + 1.0 / L)
    for p, L in estimated.items():
        Z = (1j * 2 * np.pi * f * L)[:, None, None]
        e = t2s(series_t(Z))
        k = p - 1
        Se[:, k, k], Se[:, k, N + k], Se[:, N + k, k], Se[:, N + k, N + k] = e[:, 0, 0], e[:, 0, 1], e[:, 1, 0], e[:, 1, 1]
        method[p] = f'estimated port inductance {L * 1e12:.3g} pH'
    lines = [f'port {p}: {method.get(p, "not de-embedded (no port geometry data)")}' for p in range(1, N + 1)]
    return Se, lines


def calibrated_deembedding(snp_filename, port_info, sim_path):
    """de-embedding of a model with port walls: calibrated at the walls, estimated port inductance elsewhere. Writes
    <name>_deembedded.sNp with one comment line per port, and <name>_deembedding.json with the port elements, the line
    of each wall and the diagnostics"""
    unit = port_info.get('unit', 1e-6)
    groups = port_info['port_walls']
    try:
        groups_cal = [(g, _calibrate_group(g, sim_path, unit)) for g in groups]
    except (OSError, ValueError, KeyError) as error:
        print(f'ERROR: calibrated de-embedding not possible: {error}')
        print('       The calibration standards are solved by run_sim before the device. No de-embedded file written.')
        return
    ntwk = rf.Network(snp_filename)
    z0 = ntwk.z0.copy()
    f = ntwk.f
    N = ntwk.nports
    ntwk.renormalize(50)
    Se, lines = _error_network(f, N, port_info, groups_cal, unit)
    S = deembed_s(ntwk.s, Se)
    out = rf.Network(frequency=ntwk.frequency, s=S, z0=50, name=ntwk.name)
    out.renormalize(z0)
    out.comments = '\n'.join(lines)
    filename, file_extension = os.path.splitext(snp_filename)
    out_filename = filename + '_deembedded' + file_extension
    out.write_touchstone(out_filename, skrf_comment=True, form='db', write_noise=True)
    print('Created de-embedded file: ', out_filename)
    for line in lines:
        print('  ' + line)

    sidecar = {'file': os.path.basename(out_filename), 'ports': lines, 'port_walls': []}
    for g, cal in groups_cal:
        w = 2 * np.pi * cal['f']
        entry = {'side': g['side'], 'ports': g['ports'], 'D': g.get('D'), 'L': g['L'], 'shift': g.get('shift', 0.0),
                 'extension': g.get('extension', 0.0),
                 'gaps': {str(p['portnumber']): p['gap'] for p in g.get('port_details', [])},
                 'frequencies_GHz': (cal['f'] / 1e9).tolist(),
                 'port_C_fF': (cal['Ys'].imag / w[:, None, None] * 1e15).round(4).tolist(),
                 'port_G_mS': (cal['Ys'].real * 1e3).round(5).tolist(),
                 'port_series_L_pH': (cal['Zs'].imag / w[:, None, None] * 1e12).round(4).tolist(),
                 'line': [{'mode': m['mode'],
                           'Z0_ohm': None if m['Z0'] is None else [round(float(abs(z)), 3) for z in m['Z0']],
                           'n_eff': [round(float(x), 4) for x in m['n_eff']],
                           'loss_dB_per_mm': [round(float(x), 4) for x in m['loss_dB_per_mm']]} for m in cal['report']],
                 'valid_to_GHz': round(cal['valid_to_GHz'], 3),
                 'warnings_from_generation': g.get('warnings', []), 'calibration_doubtful': cal['doubtful']}
        sidecar['port_walls'].append(entry)
        mid = len(cal['f']) // 2
        modes = ', '.join(f"{m['mode']}" + (f" Z0 {abs(m['Z0'][mid]):.4g} ohm" if m['Z0'] is not None else '') +
                          f", n_eff {m['n_eff'][mid]:.4g}, loss {m['loss_dB_per_mm'][mid]:.3g} dB/mm" for m in cal['report'])
        print(f"  feed line at port wall {g['side']}, {cal['f'][mid] / 1e9:.4g} GHz: {modes}")
        print(f"  calibration valid up to about {cal['valid_to_GHz']:.4g} GHz")
        for warning in cal['doubtful']:
            print(f"  WARNING, calibration doubtful: {warning}")
    with open(filename + '_deembedding.json', 'w', encoding='utf-8') as fh:
        json.dump(sidecar, fh, indent=2)


def _standard_folder_of(found_filename, port_info_data):
    """the name of the calibration standard whose result this is, or None"""
    parts = set(os.path.normpath(found_filename).split(os.sep))
    for group in port_info_data.get('port_walls', []):
        for standard in group.get('standards', []):
            if standard.get('model') in parts:
                return standard['name']
    return None


__version__ = "1.3.1"    # 1.3: port wall calibration (gds2palace 0.10.0); 1.3.1: --help, --version, folder argument
                         # printed at the start so a log shows which copy ran


def cli(argv=None):
    """Command line: python combine_extend_snp.py [folder]. Returns the exit code."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="combine_extend_snp.py",
        description="Convert Palace (port-S.csv) and Elmer (scalar_results) S-parameter results to Touchstone "
                    ".sNp files. Searches the folder and all folders below it. Also writes a DC-extrapolated "
                    "_dc.sNp when the data starts at low frequency, and de-embedded files when the model's "
                    "port_information.json asks for it.")
    parser.add_argument("folder", nargs="?", default=None,
                        help="folder to search (default: the current folder)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    workdir = os.path.abspath(args.folder) if args.folder else os.getcwd()
    if not os.path.isdir(workdir):
        print(f"combine_extend_snp.py: error: folder not found: {workdir}", file=sys.stderr)
        return 2
    main(workdir)
    return 0


def main(workdir=None):
    """Convert all results in workdir (default: the current folder) and the folders below it."""
    print(f"combine_extend_snp.py {__version__} ({os.path.abspath(__file__)})")
    global found_datafiles

    if workdir is None:
        workdir = os.getcwd()
    found_datafiles = []

    # work recursively through directories
    traverse_directories(workdir)

    # evaluate the found data files
    for found_filename in found_datafiles:
        _process_datafile(found_filename)


def _process_datafile(found_filename):
    # print(str(f))

    # Before we evaluate S-parameters, also check if we have a file port_information.json
    # Search upward from the data file's directory, since it can be one level
    # further down for AMR iteration folders (.../output/<model>/iterationN/port-S.csv)
    # than for a normal run (.../output/<model>/port-S.csv). Capped at a small fixed
    # depth so we never wander off into unrelated directories further up the tree.
    port_info_available = False
    MAX_LEVELS_UP = 4
    search_dir = os.path.abspath(os.path.dirname(found_filename))
    port_info_filename = None
    for _ in range(MAX_LEVELS_UP):
        search_dir = os.path.abspath(os.path.join(search_dir, ".."))
        candidate = os.path.join(search_dir, "port_information.json")
        if os.path.isfile(candidate):
            port_info_filename = candidate
            break

    # If we found the port file within MAX_LEVELS_UP directories above
    if port_info_filename is not None:
        print(f"Found extra file with port information: {port_info_filename}")

        # Load the JSON data
        with open(port_info_filename, "r") as f:
            port_info_data = json.load(f)

        # Extract all Z0 values, in port number order (the order of the S-matrix); one per port: a multielement
        # port has one entry per element
        ports_with_Z0 = sorted({port.get("portnumber", 0): port for port in port_info_data.get("ports", [])
                                if "Z0" in port}.values(),
                               key=lambda port: port.get("portnumber", 0))
        Z0_values = [port["Z0"] for port in ports_with_Z0]
        print("Port Z0 values found:", Z0_values)

        # Touchstone option line: one value if all ports have the same Z0, otherwise one value
        # per port, in port order (before, ports with the same Z0 as port 1 were left out)
        if all(Z == Z0_values[0] for Z in Z0_values):
            Z0_string = str(Z0_values[0])
        else:
            Z0_string = ' '.join(str(Z) for Z in Z0_values)
        port_info_available = True
        print("Port impedance for Touchstone header: ", Z0_string)

        # results of calibration standards are not devices: they are read by the device's de-embedding
        standard = _standard_folder_of(found_filename, port_info_data)
        if standard is not None:
            print(f'Calibration standard {standard}: used by the de-embedding of {port_info_data.get("name", "the device")}')
            return

        # We might also get the model basename from the port information file. 
        # This can be useful for Elmer files where the output file and directory 
        # name is always "mesh"
        modelname_from_portinfo = port_info_data.get("name", "")

    else:
        Z0_string = "50"       # default 
        modelname_from_portinfo = ""


    # data file items
    freq = []
    S_dB = []
    S_arg = []
    freq_unit = ''
    num_ports = 0

    if 'port-S.csv' in found_filename:
        # Palace
        num_ports, freq_unit = parse_palace_csv(found_filename, freq, S_dB, S_arg)
    elif 'scalar_results' in found_filename:
        # Elmer
        num_ports, freq_unit = parse_elmer_results(found_filename, freq, S_dB, S_arg)
    else:
        print('Invalid file, exit')    
        exit(1)

    data_lines = []
    
    incomplete_points = []

    for frequency in freq:
        # line = str(frequency)

        index = freq.index(frequency)
        data_line = [frequency]

        for i in range(1,num_ports+1):
            for j in range(1, num_ports+1):

                # special case 2-port data: the output is S11 S21 S12 S22
                if num_ports==2:
                    param = str(j) + ' ' + str(i)
                else:
                    param = str(i) + ' ' + str(j)

                found_params = S_dB[index].keys()
                raw_dB = S_dB[index].get(param) if param in found_params else None
                # Palace writes the literal string "NULL" for an excitation that
                # had not been solved yet when the solver run was interrupted
                # (e.g. terminated after exceeding a memory limit). Treat that
                # the same as a genuinely missing parameter below, rather than
                # writing "NULL" into the Touchstone file, where it would only
                # surface later as an unhandled parse error in skrf
                if raw_dB is not None and raw_dB != 'NULL':
                    Sij_dB  = raw_dB
                    Sij_arg = S_arg[index].get(param)
                else:
                    Sij_dB  = 0.0
                    Sij_arg = 0.0
                    if raw_dB == 'NULL':
                        incomplete_points.append((frequency, param))
                # write Sij data
                data_line.append (Sij_dB)
                data_line.append( Sij_arg)

        data_lines.append(data_line)

    if incomplete_points:
        print(f'WARNING: solver run was interrupted before all excitations finished - '
              f'{len(incomplete_points)} S-parameter value(s) were not computed and were '
              f'set to 0.0 dB / 0 deg instead: {incomplete_points}')

    # sort data_lines by frequency (first value)
    data_lines.sort(key=lambda x:float(x[0]))

    # get directory where port-S.csv file is stored
    data_path = os.path.dirname(found_filename)
    output_path = data_path

    # get name of parent diretory, so that we can use it as filename for output 
    splitpath =  os.path.split(data_path)
    parentname = splitpath[1]
    
    # for Elmer, parent name might be "mesh", then we can try to get meaningful name 
    # from port information file
    if parentname == 'mesh' and modelname_from_portinfo != '':
        parentname = modelname_from_portinfo

     
    output_filename = parentname + '.s' + str(num_ports) + 'p'   
    output_filename = os.path.join(output_path, output_filename)


    output_file = open(output_filename, "w")
    # comment lines must come before the option ('#') line for compatibility
    # with strict Touchstone readers
    if incomplete_points:
        incomplete_params = sorted({'S' + param.replace(' ', '') for _freq, param in incomplete_points})
        output_file.write(f"! WARNING: incomplete S-parameters, solver run was interrupted - "
                           f"{', '.join(incomplete_params)} set to 0.0 dB / 0 deg\n")
    # write Touchstone header line
    output_file.write(f"#  {freq_unit.upper()} S DB R {Z0_string}\n")

    for data_line in data_lines:
        line = ''
        for value in data_line:
            line = line + ' ' + str(value)
        output_file.write(line + "\n")

    output_file.close() 
    print('Created combined S-parameter file for ', num_ports, 'ports, filename: ', output_filename)

    if not port_info_available:
        print('NOTE: Port impedance not listed in Palace file, assuming 50 Ohm!')
        print('      If required, you can change that value in Touchstone file header!\n')

    # try DC extrapolation
    dc_extrapolated_filename = extrapolate_to_DC(output_filename)

    # port de-embedding: calibrated at port walls (with the estimated port inductance at the other ports), otherwise
    # the estimated port inductance only; settings['deembedding'] = 'none' keeps the raw result only
    if port_info_available and port_info_data.get('deembedding') != 'none':
        filenames = [output_filename]
        if dc_extrapolated_filename != '' and os.path.isfile(dc_extrapolated_filename):
            # dc_extrapolated_filename already includes the .sNp extension now
            filenames.append(dc_extrapolated_filename)
        for filename in filenames:
            if port_info_data.get('port_walls'):
                calibrated_deembedding(filename, port_info_data, os.path.dirname(port_info_filename))
            else:
                port_deembedding(filename, port_info_available, port_info_data)


if __name__ == "__main__":
    sys.exit(cli())

