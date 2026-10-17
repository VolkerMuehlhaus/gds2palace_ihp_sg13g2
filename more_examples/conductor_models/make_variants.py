"""Write the model scripts of the conductor model study from the 2 um base scripts of the mesh convergence studies and
the L6n2 v3 study. Each variant script is the base script with:
  - settings['conductor_model'] = 'surface' | 'solve_inside' | 'solve_inside_skin', or settings['filled_metals'] = 'auto'
  - refined_cellsize set to the variant's mesh size
  - the GDSII and stackup paths pointing to the base study folder (no copies of these files here)
The scripts are written into one folder per structure; run them with:  python <script> nogui
Usage (palace venv, this folder):  python make_variants.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MC = os.path.join('..', '..', 'mesh_convergence')
L6 = os.path.join('..', '..', 'measured_vs_simulated', 'more_accurate_models_L6n2_v3')

MODELS = {   # variant suffix: (line added to the settings, refined_cellsize)
    'surface_mesh2': ("settings['conductor_model'] = 'surface'", 2.0),
    'auto_mesh2': ("settings['filled_metals'] = 'auto'  # expert setting: only layers thinner than refined_cellsize as volumes", 2.0),
    'solve_inside_mesh2': ("settings['conductor_model'] = 'solve_inside'", 2.0),
    'solve_inside_skin_mesh2': ("settings['conductor_model'] = 'solve_inside_skin'", 2.0),
    'solve_inside_skin_mesh3': ("settings['conductor_model'] = 'solve_inside_skin'", 3.0),
    'solve_inside_skin_mesh5': ("settings['conductor_model'] = 'solve_inside_skin'", 5.0),
}

STRUCTURES = {   # folder: (base script, source folder, model name prefix, variants)
    'inductor': ('palace_ind_frame_mesh2.py', os.path.join(MC, 'mesh_convergence_inductor'), 'ind_frame',
                 # no 'auto': the coil has no shapes on layers thinner than 2 um, 'auto' builds the surface model
                 ['surface_mesh2', 'solve_inside_mesh2', 'solve_inside_skin_mesh2', 'solve_inside_skin_mesh5']),
    'transformer': ('palace_transformer_imn_mesh2.py', os.path.join(MC, 'mesh_convergence_transformer'), 'transformer',
                    ['surface_mesh2', 'auto_mesh2', 'solve_inside_mesh2', 'solve_inside_skin_mesh2']),
    'dband_balun': ('palace_balun_mesh2.py', os.path.join(MC, 'mesh_convergence_D-band_balun'), 'dband_balun',
                    ['surface_mesh2', 'auto_mesh2', 'solve_inside_mesh2', 'solve_inside_skin_mesh2']),
    'mim_balun': ('trans_100diff_to_80se_ports_mesh2.py', os.path.join(MC, 'mesh_convergence_balun_mim'), 'mim_balun',
                  ['surface_mesh2', 'auto_mesh2', 'solve_inside_mesh2', 'solve_inside_skin_mesh2', 'solve_inside_skin_mesh3']),
    'balun2x1': ('balun2x1_edgecoupled_do200_w8_s2_mesh2.py', os.path.join(MC, 'mesh_convergence_balun2x1'), 'balun2x1',
                 ['surface_mesh2', 'auto_mesh2', 'solve_inside_mesh2', 'solve_inside_skin_mesh2']),
    'l6n2': ('L6n2_with_ports_2um_passi3D.py', L6, 'l6n2',
             ['surface_mesh2', 'auto_mesh2', 'solve_inside_mesh2']),
}

CONDUCTOR_SETTINGS = re.compile(r"^settings\['(filled_metals|skin_layers|conductor_model)'\].*\n", re.M)
CELLSIZE = re.compile(r"^(settings\['refined_cellsize'\]\s*=\s*)[0-9.]+(.*)$", re.M)
PATHS = re.compile(r"^((?:settings\['(?:GdsFile|SubstrateFile)'\]|gds_filename|XML_filename)\s*=\s*)(['\"])([^'\"]+)\2", re.M)


def variant_script(base_text, src_dir, base_name, variant):
    line, cellsize = MODELS[variant]
    text = CONDUCTOR_SETTINGS.sub('', base_text)
    text, n = CELLSIZE.subn(lambda m: f"{m.group(1)}{cellsize:g}{m.group(2)}\n{line}", text, count=1)
    assert n == 1, 'no refined_cellsize line'
    src = src_dir.replace(os.sep, '/')
    text, n = PATHS.subn(lambda m: f"{m.group(1)}{m.group(2)}{src}/{m.group(3)}{m.group(2)}", text)
    assert n == 2, f'expected GDSII and stackup path, found {n}'
    # the relative paths need this folder as working directory (some base scripts change to it later, some never)
    text = text.replace('from gds2palace import *\n',
                        'from gds2palace import *\n\nos.chdir(os.path.dirname(os.path.abspath(__file__)))\n', 1)
    assert 'os.chdir(os.path.dirname(os.path.abspath(__file__)))' in text
    header = (f"# Conductor model study: {variant.replace('_mesh', ', ').rstrip('0123456789, ')} at "
              f"refined_cellsize {cellsize:g} um\n"
              f"# Written by make_variants.py from {src}/{base_name}; edit the base script or the generator, not this file.\n")
    return header + text


def main():
    count = 0
    for folder, (base_name, src_dir, prefix, variants) in STRUCTURES.items():
        os.makedirs(os.path.join(HERE, folder), exist_ok=True)
        base_path = os.path.normpath(os.path.join(HERE, folder, src_dir, base_name))
        assert os.path.exists(base_path), f'base script missing: {base_path}'
        base = open(base_path, encoding='utf-8').read()
        for v in variants:
            path = os.path.join(HERE, folder, f'{prefix}_{v}.py')
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(variant_script(base, src_dir, base_name, v))
            count += 1
    print(count, 'scripts written')


if __name__ == '__main__':
    main()
