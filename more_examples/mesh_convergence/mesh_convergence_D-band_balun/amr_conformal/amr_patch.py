"""Edit the AMR settings of a config.json written by gds2palace, for this study.

gds2palace writes a fixed "UpdateFraction": 0.7 and always uses the frequency sweep of the model script for AMR.
This study needs other values, so the model scripts call patch_config() after create_palace().

patch_config() keeps the unchanged file as config_original.json, so that make_stage2.py can restore the full
frequency sweep for the second stage.
"""
import json
import os
import shutil


def patch_config(config_name, update_fraction, conformal, max_its, max_size=2e6, save_mesh=False,
                 single_freq_GHz=None):
    """Set the AMR settings in config_name. With single_freq_GHz, AMR (and the whole run) uses only this frequency.

    The mesh is not touched: it was built with the full 100-200 GHz sweep, so all variants start from the same mesh.
    """
    original = os.path.join(os.path.dirname(config_name), 'config_original.json')
    shutil.copy(config_name, original)
    with open(config_name) as f:
        config = json.load(f)

    refinement = config['Model']['Refinement']
    new = {'UpdateFraction': update_fraction, 'Nonconformal': not conformal, 'MaxIts': max_its,
           'MaxSize': max_size, 'SaveAdaptMesh': save_mesh}
    print('AMR settings for this study:')
    for key, value in new.items():
        print(f'  Refinement.{key}: {refinement.get(key)} -> {value}')
        refinement[key] = value

    if single_freq_GHz is not None:
        driven = config['Solver']['Driven']
        driven['Samples'] = [{'Type': 'Point', 'Freq': [single_freq_GHz], 'SaveStep': 0}]
        # one frequency: no adaptive frequency sweep
        driven.pop('AdaptiveTol', None)
        print(f'  Driven.Samples: single frequency {single_freq_GHz} GHz, adaptive frequency sweep off')

    with open(config_name, 'w') as f:
        json.dump(config, f, indent=4)
