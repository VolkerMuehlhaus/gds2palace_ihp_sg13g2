"""The gmsh model of the shipped examples, built without meshing: every layer of the layout must be in the model with
the size that follows from the layout and the stackup, every port of the script must be there, and the conductors
must form as many separate nets as in the layout. Nothing is compared with an earlier run.

    python -m pytest tests/test_examples_geometry.py
"""
import copy

import pytest

import example_runner as er
from gds2palace import util_gds_reader as reader

GEOMETRY = [e['script'] for e in er.load_manifest() if 'geometry' in e['tiers']]


@pytest.mark.parametrize('script', GEOMETRY)
def test_model_geometry_matches_layout_and_stackup(script, tmp_path):
    run = er.run_example(script, tmp_path, mode='geometry')
    # one model per read_gds() call; a script may build several (one per temperature, ...)
    assert len(run.read_calls) == len(run.create_calls) == len(run.groups) >= 1, run.log[-2000:]
    for call, settings, groups, nets in zip(run.read_calls, run.create_calls, run.groups, run.nets):
        problems, skipped = er.compare_with_model(call, settings, groups)
        assert not problems, settings['model_basename'] + ': ' + '; '.join(problems)
        assert nets == er.layout_nets(call), settings['model_basename'] + ': separate conductor nets: model, layout'


# ---- the checks above must fail for the bugs they are there for ----

def test_checks_catch_a_via_array_merged_across_two_lines(monkeypatch, tmp_path):
    """Without the reader's protection (split_bridging_via_merges), the two via rows of the fixture merge into one
    block that shorts the two lines: one net in the model, two in the layout."""
    script = 'tests/data/via_bridge_model.py'
    run = er.run_example(script, tmp_path / 'ok', mode='geometry')
    assert run.nets[0] == er.layout_nets(run.read_calls[0]) == 2
    monkeypatch.setattr(reader, 'split_bridging_via_merges', lambda merged, *args, **kwargs: (merged, 0, 0))
    run = er.run_example(script, tmp_path / 'bridged', mode='geometry')
    assert run.nets[0] == 1 and er.layout_nets(run.read_calls[0]) == 2


def test_checks_catch_a_shape_missing_in_the_model(tmp_path):
    """the comparison of model and reader output, tried on records that no longer fit the model"""
    run = er.run_example('tests/data/dipole_model.py', tmp_path, mode='geometry')
    call, settings, groups = run.read_calls[0], run.create_calls[0], run.groups[0]
    assert er.compare_with_model(call, settings, groups)[0] == []

    def without(layer, count=None):
        changed = dict(call, result=copy.copy(call['result']))
        on_layer = [p for p in call['result'].polygons if int(p.layernum) == layer]
        dropped = on_layer if count is None else on_layer[:count]
        changed['result'].polygons = [p for p in call['result'].polygons if not any(p is d for d in dropped)]
        return changed

    problems, _ = er.compare_with_model(without(19, 1), settings, groups)         # one of the two Via1 blocks
    assert len(problems) == 2 and problems[0].startswith('Via1: bounding box') and problems[1].startswith('Via1: volume')
    problems, _ = er.compare_with_model(without(10), settings, groups)            # all of Metal2
    assert problems == ['Metal2: in the model, but nothing returned by the reader on layer 10']
    problems, _ = er.compare_with_model(without(201), settings, groups)           # the port shape
    assert problems == ['port 1: in the model, but nothing drawn on layer 201']
    smaller = {key: (dict(g, mass=g['mass'] - 2 * 3790) if key == (2, 'Metal1_1') else g) for key, g in groups.items()}
    problems, _ = er.compare_with_model(call, settings, smaller)                  # the strip of the 0.10.3 fix
    assert len(problems) == 1 and problems[0].startswith('Metal1: surface')
