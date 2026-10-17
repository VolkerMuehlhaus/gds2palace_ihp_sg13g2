"""Build the Palace models of all study scripts (mesh + config.json), one after another, with one log per model in
build_logs/. Models that already have a config.json are skipped. Then builds the line models (lines/make_line_models.py).
Usage (palace venv, this folder):  python build_models.py [name part ...]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDERS = ['inductor', 'transformer', 'dband_balun', 'mim_balun', 'balun2x1', 'l6n2']
LOGS = os.path.join(HERE, 'build_logs')


def main(parts):
    os.makedirs(LOGS, exist_ok=True)
    for folder in FOLDERS:
        for script in sorted(f for f in os.listdir(os.path.join(HERE, folder)) if f.endswith('.py')):
            name = script[:-3]
            if parts and not any(p in name for p in parts):
                continue
            if os.path.exists(os.path.join(HERE, folder, 'palace_model', name + '_data', 'config.json')):
                continue
            print('building', name, flush=True)
            with open(os.path.join(LOGS, name + '.log'), 'w') as log:
                r = subprocess.run([sys.executable, script, 'nogui'], cwd=os.path.join(HERE, folder),
                                   stdout=log, stderr=subprocess.STDOUT)
            print('   ', 'ok' if r.returncode == 0 else f'FAILED ({r.returncode})', flush=True)
    if not parts or any('line' in p for p in parts):
        with open(os.path.join(LOGS, 'lines.log'), 'w') as log:
            subprocess.run([sys.executable, 'make_line_models.py'], cwd=os.path.join(HERE, 'lines'),
                           stdout=log, stderr=subprocess.STDOUT)
        print('lines done', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
