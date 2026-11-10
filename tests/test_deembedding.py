"""Calibrated de-embedding in scripts/combine_extend_snp.py, checked with ideal circuits: a known port, line and device
are turned into Palace result files, and the de-embedding must give the device back. No Palace needed.

    python -m pytest tests/test_deembedding.py
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import combine_extend_snp as ce  # noqa: E402
import skrf as rf  # noqa: E402

F_DEV = np.linspace(1e9, 100e9, 12)
F_STD = np.array([5e9, 20e9, 100e9])
UNIT = 1e-6


def port_elements(f):
    """a 2-line port group: shunt C with coupling, small series L with coupling"""
    w = 2 * np.pi * f[:, None, None]
    C = np.array([[3.0e-15, -0.4e-15], [-0.4e-15, 2.8e-15]])
    Ls = np.array([[0.20e-12, 0.05e-12], [0.05e-12, 0.25e-12]])
    return 1j * w * C, 1j * w * Ls


def line_t(f, length, loss=False):
    """coupled 2-line section, length in drawing units: T = expm(K length), K = [[0, Z'], [Y', 0]]"""
    w = 2 * np.pi * f[:, None, None]
    Lp = np.array([[0.45e-6, 0.10e-6], [0.10e-6, 0.45e-6]])           # H/m
    Cp = np.array([[0.20e-9, -0.04e-9], [-0.04e-9, 0.20e-9]])         # F/m
    Zp = 1j * w * Lp + (np.eye(2) * 2e3 * np.sqrt(f[:, None, None] / 1e9) if loss else 0)
    Yp = 1j * w * Cp
    K = ce._join(np.zeros_like(Zp), Zp, Yp, np.zeros_like(Yp)) * (length * UNIT)
    return ce._eig_fun(K, np.exp)


def dut_s(f):
    """a reciprocal, lossy 2-port: a coil-like series RL between the two ports with shunt C to ground at both"""
    w = 2 * np.pi * f
    z = 2.0 + 1j * w * 230e-12
    y = 1j * w * 20e-15
    Y = np.zeros((len(f), 2, 2), dtype=complex)
    Y[:, 0, 0] = Y[:, 1, 1] = 1 / z + y
    Y[:, 0, 1] = Y[:, 1, 0] = -1 / z
    I = np.eye(2)
    return (I - 50 * Y) @ np.linalg.inv(I + 50 * Y)


def embed(S_dut, Se):
    s11, s12, s21, s22 = ce._blocks(Se)
    I = np.eye(S_dut.shape[-1])
    return s11 + s12 @ S_dut @ np.linalg.inv(I - s22 @ S_dut) @ s21


def write_palace_csv(path, f, S):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = S.shape[-1]
    names = [(i, j) for j in range(n) for i in range(n)]
    head = '        f (GHz),' + ''.join(f'  |S[{i + 1}][{j + 1}]| (dB),  arg(S[{i + 1}][{j + 1}]) (deg.),' for i, j in names)
    with open(path, 'w') as fh:
        fh.write(head + '\n')
        for k in range(len(f)):
            row = [f'{f[k] / 1e9:.8e}']
            for i, j in names:
                row += [f'{20 * np.log10(abs(S[k, i, j])):+.12e}', f'{np.degrees(np.angle(S[k, i, j])):+.12e}']
            fh.write(', '.join(row) + ',\n')


def make_case(tmp_path, shift=0.0, loss=False, interior=False, extension=0.0):
    """sim folder with port_information.json, the two standards' results and the device's result"""
    sim = tmp_path / 'dev_data'
    L = 200.0
    Ys, Zs = port_elements(F_STD)
    P = ce.shunt_t(Ys) @ ce.series_t(Zs)
    for name, factor in (('cal_xmin_L', 1), ('cal_xmin_2L', 2)):
        T = P @ line_t(F_STD, factor * L, loss) @ ce.rev_t(P)
        write_palace_csv(str(sim / 'output' / f'dev_{name}' / 'port-S.csv'), F_STD, ce.t2s(T))
    Ys, Zs = port_elements(F_DEV)
    E = ce.shunt_t(Ys) @ ce.series_t(Zs) @ line_t(F_DEV, shift + extension, loss)
    S_dut = dut_s(F_DEV)
    if interior:
        # 3-port device: ports 1 and 3 on the wall, port 2 interior with the estimated port inductance
        S3 = np.zeros((len(F_DEV), 3, 3), dtype=complex)
        S3[:, np.ix_([0, 2], [0, 2])[0], np.ix_([0, 2], [0, 2])[1]] = S_dut
        S3[:, 1, 1] = -0.3 + 0.2j
        S_dut = S3
        Lest = ce.flat_strip_inductance(1.0, 10.0, 0, UNIT)
        e_wall = ce.t2s(E)
        e_int = ce.t2s(ce.series_t((1j * 2 * np.pi * F_DEV * Lest)[:, None, None]))
        Se = np.zeros((len(F_DEV), 6, 6), dtype=complex)
        for a, pa in enumerate([0, 2]):
            for b, pb in enumerate([0, 2]):
                Se[:, pa, pb], Se[:, pa, 3 + pb] = e_wall[:, a, b], e_wall[:, a, 2 + b]
                Se[:, 3 + pa, pb], Se[:, 3 + pa, 3 + pb] = e_wall[:, 2 + a, b], e_wall[:, 2 + a, 2 + b]
        Se[:, 1, 1], Se[:, 1, 4], Se[:, 4, 1], Se[:, 4, 4] = e_int[:, 0, 0], e_int[:, 0, 1], e_int[:, 1, 0], e_int[:, 1, 1]
        ports_wall = [1, 3]
    else:
        Se = ce.t2s(E)
        ports_wall = [1, 2]
    S_meas = embed(S_dut, Se)
    write_palace_csv(str(sim / 'output' / 'dev' / 'port-S.csv'), F_DEV, S_meas)
    ports = [{'portnumber': p, 'Z0': 50, 'length': 1.0, 'width': 10.0, 'element': 1} for p in range(1, S_dut.shape[-1] + 1)]
    info = {'ports': ports, 'unit': UNIT, 'name': 'dev', 'port_walls': [{
        'side': 'xmin', 'ports': ports_wall, 'D': 50.0, 'L': L, 'shift': shift, 'extension': extension, 'eps_max': 11.9,
        'port_details': [{'portnumber': p, 'gap': 1.0} for p in ports_wall], 'warnings': [],
        'standards': [{'name': n, 'model': f'dev_{n}', 'output': f'output/dev_{n}', 'length': L * k}
                      for n, k in (('cal_xmin_L', 1), ('cal_xmin_2L', 2))]}]}
    (sim / 'port_information.json').write_text(json.dumps(info))
    return sim, S_dut


def run_combine(sim):
    cwd = os.getcwd()
    try:
        os.chdir(sim)
        ce.main()
    finally:
        os.chdir(cwd)


def test_round_trip_s_t():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(3, 4, 4)) + 1j * rng.normal(size=(3, 4, 4))
    S = 0.3 * (A + A.swapaxes(-1, -2)) / 2
    assert np.max(np.abs(ce.t2s(ce.s2t(S)) - S)) < 1e-12


def test_deembed_s_inverts_embedding():
    Ys, Zs = port_elements(F_DEV)
    Se = ce.t2s(ce.shunt_t(Ys) @ ce.series_t(Zs))
    S = dut_s(F_DEV)
    assert np.max(np.abs(ce.deembed_s(embed(S, Se), Se) - S)) < 1e-10


def test_deembed_s_at_dc_with_a_shorted_device():
    """at DC the coil is a short between its ports: Y is singular, the S-domain removal is not"""
    S = np.array([[[0, 1], [1, 0]]], dtype=complex)
    Se = ce.t2s(ce.shunt_t(np.zeros((1, 2, 2), dtype=complex)) @ ce.series_t(np.zeros((1, 2, 2), dtype=complex)))
    assert np.max(np.abs(ce.deembed_s(S, Se) - S)) < 1e-12


@pytest.mark.parametrize('shift', [0.0, 60.0])
def test_calibrated_deembedding_recovers_the_device(tmp_path, shift):
    sim, S_dut = make_case(tmp_path, shift=shift)
    run_combine(sim)
    out = rf.Network(str(sim / 'output' / 'dev' / 'dev_deembedded.s2p'))
    assert np.max(np.abs(out.s - S_dut)) < 1e-6
    text = (sim / 'output' / 'dev' / 'dev_deembedded.s2p').read_text()
    where = 'at the wall' if not shift else '60 um into the layout'
    assert f'!port 1: calibrated at port wall xmin, reference plane {where}' in text
    side = json.loads((sim / 'output' / 'dev' / 'dev_deembedding.json').read_text())
    wall = side['port_walls'][0]
    assert abs(wall['port_C_fF'][1][0][0] - 3.0) < 1e-3 and abs(wall['port_series_L_pH'][1][1][1] - 0.25) < 1e-3
    assert [m['mode'] for m in wall['line']] == ['common', 'differential']
    assert wall['calibration_doubtful'] == []


def test_standards_are_not_processed_as_devices(tmp_path):
    sim, _ = make_case(tmp_path)
    run_combine(sim)
    assert not list((sim / 'output' / 'dev_cal_xmin_L').glob('*.s*p'))


def test_interior_port_gets_the_estimated_inductance(tmp_path):
    sim, S_dut = make_case(tmp_path, interior=True)
    run_combine(sim)
    out = rf.Network(str(sim / 'output' / 'dev' / 'dev_deembedded.s3p'))
    assert np.max(np.abs(out.s - S_dut)) < 1e-6
    text = (sim / 'output' / 'dev' / 'dev_deembedded.s3p').read_text()
    assert '!port 2: estimated port inductance' in text and 'Terman' not in text


def test_lossy_line_with_shift_is_close(tmp_path):
    """the line's A is interpolated between the standards' frequencies: with skin effect loss not exact, but close"""
    sim, S_dut = make_case(tmp_path, shift=60.0, loss=True)
    run_combine(sim)
    out = rf.Network(str(sim / 'output' / 'dev' / 'dev_deembedded.s2p'))
    assert np.max(np.abs(out.s - S_dut)) < 2e-3


def test_missing_standards_write_no_deembedded_file(tmp_path, capsys):
    sim, _ = make_case(tmp_path)
    os.remove(sim / 'output' / 'dev_cal_xmin_2L' / 'port-S.csv')
    run_combine(sim)
    assert not (sim / 'output' / 'dev' / 'dev_deembedded.s2p').exists()
    assert 'calibrated de-embedding not possible' in capsys.readouterr().out


def test_extension_puts_the_reference_plane_back_at_the_layout_edge(tmp_path):
    """the port wall moved 40 outward: the extended feed is removed like a shift"""
    sim, S_dut = make_case(tmp_path, extension=40.0)
    run_combine(sim)
    out = rf.Network(str(sim / 'output' / 'dev' / 'dev_deembedded.s2p'))
    assert np.max(np.abs(out.s - S_dut)) < 1e-6
    text = (sim / 'output' / 'dev' / 'dev_deembedded.s2p').read_text()
    assert 'reference plane at the layout edge (port wall moved 40 um outward, feed extended)' in text
