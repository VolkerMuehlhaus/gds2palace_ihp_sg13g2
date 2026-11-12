"""The model files of the shipped examples, with meshing: the files are written, mesh and config.json fit together,
the ports are those of the script, and config.json, the mesh groups and port_information.json are as stored in
tests/golden/. A change that alters them on purpose updates the stored files:

    UPDATE_GOLDEN=1 python -m pytest tests/test_examples_model.py -m examples

and the diff of tests/golden/ in the commit shows what changed. Marked "examples" (meshing takes minutes): not part
of a plain "python -m pytest tests".
"""
import json
import os

import pytest

import example_runner as er

MODEL = [e['script'] for e in er.load_manifest() if 'model' in e['tiers']]
GOLDEN = os.path.join(er.TESTS, 'golden')


@pytest.mark.examples
@pytest.mark.parametrize('script', MODEL)
def test_model_files(script, tmp_path):
    run = er.run_example(script, tmp_path, mode='model')
    assert len(run.create_calls) == 1, run.log[-2000:]
    settings = run.create_calls[0]
    data_dir, model = settings['sim_path'], settings['model_basename']
    problems = er.check_model_files(data_dir, model, settings)
    assert not problems, '; '.join(problems) + '\n' + run.log[-1500:]

    record = er.model_record(data_dir, model)
    path = os.path.join(GOLDEN, model + '.json')
    if os.environ.get('UPDATE_GOLDEN'):
        os.makedirs(GOLDEN, exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(record, f, indent=1, sort_keys=True)
            f.write('\n')
        pytest.skip(f'golden file written: {os.path.basename(path)}')
    assert os.path.isfile(path), f'no golden file {os.path.basename(path)}: run once with UPDATE_GOLDEN=1'
    with open(path, encoding='utf-8') as f:
        expected = json.load(f)
    differences = er.record_differences(expected, json.loads(json.dumps(record)))
    assert not differences, 'stored -> now: ' + '; '.join(differences[:20])


# ---- the checks above must fail when the files do not fit ----

def test_checks_catch_model_files_that_do_not_fit(tmp_path):
    """the smallest model (under a second to mesh), then its config.json altered"""
    run = er.run_example('tests/data/via_bridge_model.py', tmp_path, mode='model')
    settings = run.create_calls[0]
    data_dir, model = settings['sim_path'], settings['model_basename']
    assert er.check_model_files(data_dir, model, settings) == []
    record = er.model_record(data_dir, model)
    assert er.record_differences(record, json.loads(json.dumps(record))) == []

    config_path = os.path.join(data_dir, 'config.json')
    with open(config_path, encoding='utf-8') as f:
        original = json.load(f)

    def problems_with(change):
        config = json.loads(json.dumps(original))
        change(config)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        return er.check_model_files(data_dir, model, settings)

    assert problems_with(lambda c: c['Boundaries'].pop('LumpedPort'))[-1] == 'port 1: not in config.json'
    assert any('attribute(s) [999]' in p for p in problems_with(lambda c: c['Boundaries']['Absorbing']['Attributes'].append(999)))
    assert any('without a material' in p for p in problems_with(lambda c: c['Domains']['Materials'].pop()))
    assert any(p.startswith('port 1: R = 75') for p in problems_with(lambda c: c['Boundaries']['LumpedPort'][0].update(R=75)))

    changed = json.loads(json.dumps(record))
    changed['config']['Domains']['Materials'][0]['Permittivity'] = 99.0
    changed['groups']['Extra'] = [2, 99]
    changed['tetrahedra'] = int(record['tetrahedra'] * 1.5)
    differences = er.record_differences(record, changed)
    assert len(differences) == 3 and any('Permittivity' in d for d in differences)
    changed['tetrahedra'] = int(record['tetrahedra'] * 1.1)
    assert len(er.record_differences(record, changed)) == 2            # 10 % more tetrahedra is within the band
