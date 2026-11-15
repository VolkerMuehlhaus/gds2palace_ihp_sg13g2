"""The _dc file of scripts/combine_extend_snp.py: a 0 Hz point in front of the unchanged simulated data.

    python -m pytest tests/test_dc_point.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import combine_extend_snp as ce  # noqa: E402
import skrf as rf  # noqa: E402


def series_rl_shunt_c(f):
    """2-port: series R + L between the ports, C/2 to ground at each port"""
    w = 2 * np.pi * f
    Z = 2.0 * np.sqrt(1 + f / 0.5e9) + 1j * w * 1e-9
    Y = 1j * w * 25e-15
    abcd = np.zeros((len(f), 2, 2), complex)
    abcd[:, 0, 0] = abcd[:, 1, 1] = 1 + Z * Y
    abcd[:, 0, 1] = Z
    abcd[:, 1, 0] = Y * (2 + Z * Y)
    return rf.Network(frequency=rf.Frequency.from_f(f, unit='hz'), s=rf.network.a2s(abcd), z0=50)


# as gds2palace writes a sweep from 0 Hz: two low points, then the regular steps
F_SWEEP = np.concatenate(([10e6, 20e6], np.arange(1e9, 50.5e9, 1e9)))


def test_simulated_points_are_kept():
    nw = series_rl_shunt_c(F_SWEEP)
    out = ce.network_with_dc_point(nw)
    assert out.f[0] == 0 and np.array_equal(out.f[1:], nw.f)
    assert np.array_equal(out.s[1:], nw.s)


def test_dc_value_is_real_and_the_same_as_scikit_rf():
    nw = series_rl_shunt_c(F_SWEEP)
    out = ce.network_with_dc_point(nw)
    assert np.all(out.s[0].imag == 0)
    reference = nw.extrapolate_to_dc(kind='cubic', coords='polar')
    assert np.max(np.abs(out.s[0] - reference.s[0])) < 1e-12


def test_dc_resistance_of_the_example():
    """series resistance at 0 Hz from the extrapolated point: 2 ohm in this circuit"""
    out = ce.network_with_dc_point(series_rl_shunt_c(F_SWEEP))
    assert abs((-1 / out.y[0, 1, 0]).real - 2.0) < 0.01


def test_data_starting_at_0_Hz_is_unchanged():
    nw = series_rl_shunt_c(np.arange(1e9, 30.5e9, 1e9))
    with_dc = ce.network_with_dc_point(nw)
    again = ce.network_with_dc_point(with_dc)
    assert np.array_equal(again.f, with_dc.f) and np.array_equal(again.s, with_dc.s)


def test_dc_file(tmp_path):
    name = str(tmp_path / 'model_do82.41.s2p')      # a dot in the model name must not eat the extension
    series_rl_shunt_c(F_SWEEP).write_touchstone(name)
    out_name = ce.extrapolate_to_DC(name)
    assert out_name == str(tmp_path / 'model_do82.41_dc.s2p') and os.path.isfile(out_name)
    out = rf.Network(out_name)
    assert out.f[0] == 0 and np.allclose(out.f[1:], F_SWEEP) and len(out.f) == len(F_SWEEP) + 1


def test_no_dc_file_without_low_frequency_data(tmp_path):
    name = str(tmp_path / 'band.s2p')
    series_rl_shunt_c(np.linspace(140e9, 170e9, 31)).write_touchstone(name)
    assert ce.extrapolate_to_DC(name) == ''
