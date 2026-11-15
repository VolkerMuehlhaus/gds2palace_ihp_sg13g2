"""The frequency that replaces fstart = 0: 10 MHz, higher for a very fine mesh (the solver breaks down at low
frequency there, see LOW_FREQUENCY_POINT in util_simulation_setup.py)."""

import pytest

from gds2palace import simulation_setup

low_frequency_point = simulation_setup.low_frequency_point


@pytest.mark.parametrize('cellsize', [0.5, 1, 2, 5, 50])
def test_usual_cell_sizes_keep_10_MHz(cellsize):
    assert low_frequency_point(cellsize, 1e-6) == 10e6


@pytest.mark.parametrize('cellsize, expected', [(0.2, 25e6), (0.1, 50e6), (0.05, 100e6), (0.16, 32e6)])
def test_fine_mesh_raises_the_point(cellsize, expected):
    assert low_frequency_point(cellsize, 1e-6) == pytest.approx(expected)


def test_cell_size_in_other_units():
    assert low_frequency_point(200, 1e-9) == pytest.approx(25e6)        # 0.2 um, layout in nm
    assert low_frequency_point(0.1, 1e-3) == 10e6                       # PCB in mm


def test_product_never_below_the_limit():
    for cellsize in (0.03, 0.07, 0.13, 0.3, 0.49):
        assert low_frequency_point(cellsize, 1e-6) / 1e6 * cellsize >= simulation_setup.LOW_FREQUENCY_TIMES_CELLSIZE
