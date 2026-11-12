"""The GDS reader on the shipped examples: what read_gds() returns must be the shape drawn in the GDSII file, layer by
layer. The reference is computed here from the file (gdspy), not stored from an earlier run.

    python -m pytest tests/test_examples_reader.py
"""
import glob
import os

import pytest

import example_runner as er

EXAMPLES = er.load_manifest()
READER = [e['script'] for e in EXAMPLES if 'reader' in e['tiers']]


def test_every_workflow_script_is_listed():
    listed = {e['script'] for e in EXAMPLES}
    scripts = {'workflow/' + os.path.basename(p) for p in glob.glob(os.path.join(er.REPO, 'workflow', '*.py'))}
    assert scripts - listed == set(), 'add these scripts to tests/examples.toml'
    assert listed - {s for s in listed if os.path.isfile(os.path.join(er.REPO, s))} == set(), 'listed but missing'


@pytest.mark.parametrize('script', READER)
def test_reader_returns_the_drawn_shapes(script, tmp_path):
    run = er.run_example(script, tmp_path, mode='reader')
    assert run.read_calls, 'the script did not call read_gds()\n' + run.log[-2000:]
    assert run.create_calls, 'the script did not call create_palace()\n' + run.log[-2000:]
    compared = 0
    for call in run.read_calls:
        problems, skipped = er.compare_with_layout(call)
        assert not problems, f"{os.path.basename(call['filename'])}: " + '; '.join(problems)
        assert not any(s.startswith('all') for s in skipped), skipped
        compared += len({int(p.layernum) for p in call['result'].polygons})
    assert compared > 0
