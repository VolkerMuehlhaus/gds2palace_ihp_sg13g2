"""Stage 2: full 100-200 GHz sweep on the mesh that a single-frequency AMR run (stage 1) saved.

  python make_stage2.py <stage-1 model> [<stage-1 model> ...]     e.g. palace_balun_amrc_f150_uf05

Needs the finished stage-1 run with its saved mesh in palace_model/<model>_data/output/<model>/
(python remote_runs.py collect --mesh). Writes palace_model/<model>_s2_data/ with:
  - the saved AMR mesh (Palace's MFEM format, .mesh or .meshgz), used as the model mesh
  - config.json: the stage-1 config with the original frequency sweep and adaptive sweep tolerance back
    (from config_original.json), no further AMR (MaxIts 0) and the new mesh
  - port_information.json and run_sim, as for any gds2palace model
"""
import json
import os
import shutil
import sys

from gds2palace import utilities

HERE = os.path.dirname(os.path.abspath(__file__))


def make_stage2(model):
    src = os.path.join(HERE, 'palace_model', f'{model}_data')
    name = f'{model}_s2'   # short suffix: Windows path length limit
    dst = os.path.join(HERE, 'palace_model', f'{name}_data')

    with open(os.path.join(src, 'config.json')) as f:
        config = json.load(f)
    with open(os.path.join(src, 'config_original.json')) as f:
        original = json.load(f)

    out = os.path.join(src, 'output', model)
    stem = os.path.splitext(config['Model']['Mesh'])[0]
    meshes = [f for f in os.listdir(out) if f in (stem + '.mesh', stem + '.meshgz')] if os.path.isdir(out) else []
    if not meshes:
        sys.exit(f'{model}: no saved AMR mesh in {out} (run "python remote_runs.py collect --mesh" first)')
    mesh = meshes[0]

    os.makedirs(dst, exist_ok=True)
    shutil.copy(os.path.join(out, mesh), os.path.join(dst, name + os.path.splitext(mesh)[1]))
    shutil.copy(os.path.join(src, 'port_information.json'), dst)

    config['Problem']['Output'] = f'output/{name}'
    config['Model']['Mesh'] = name + os.path.splitext(mesh)[1]
    config['Model']['Refinement'].update({'MaxIts': 0, 'SaveAdaptMesh': False})
    config['Solver']['Driven'] = original['Solver']['Driven']
    with open(os.path.join(dst, 'config.json'), 'w') as f:
        json.dump(config, f, indent=4)
    utilities.create_run_script(dst)

    driven = config['Solver']['Driven']
    print(f'{name}: mesh {config["Model"]["Mesh"]} (from {mesh}), MaxIts 0, '
          f'samples {driven["Samples"]}, AdaptiveTol {driven.get("AdaptiveTol")}')


if __name__ == '__main__':
    for m in sys.argv[1:]:
        make_stage2(m)
