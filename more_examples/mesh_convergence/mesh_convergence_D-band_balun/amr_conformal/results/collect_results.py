#!/usr/bin/env python
"""Copy the results of all finished runs from palace_model/ (not in git) to results/ (in git).

For every run, and for every AMR pass of a run:
  results/snp/<run>[_passN].s3p   de-embedded Touchstone file (from combine_extend_snp.py, run it in the
                                  _data folder first)
  results/runs.csv                unknowns, mesh elements, cumulative solve time, peak RAM, AMR error norm

The last AMR pass is the run's own output folder, so it is written as <run>.s3p, earlier passes as _passN.
Palace reports the solve time cumulatively over AMR passes: the value of the last pass covers the whole run.
"""
import csv
import glob
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PM = os.path.normpath(os.path.join(HERE, '..', 'palace_model'))  # normpath: stay below the Windows path limit
SNP = os.path.join(HERE, 'snp')


def error_norm(d):
    p = os.path.join(d, 'error-indicators.csv')
    if not os.path.exists(p):
        return ''
    with open(p) as f:
        return float(f.read().split('\n')[1].split(',')[0])


def main():
    os.makedirs(SNP, exist_ok=True)
    rows = []
    for data in sorted(glob.glob(os.path.join(PM, 'palace_balun_*_data'))):
        run = os.path.basename(data)[len('palace_balun_'):-len('_data')]
        out = os.path.join(data, 'output', f'palace_balun_{run}')
        if not os.path.exists(os.path.join(out, 'palace.json')):
            continue
        passes = sorted(glob.glob(os.path.join(out, 'iteration*')), key=lambda d: int(d.rsplit('iteration', 1)[1]))
        for k, d in enumerate(passes + [out], start=1):
            name = run if d == out else f'{run}_pass{k}'
            snp = glob.glob(os.path.join(d, '*_deembedded.s3p'))
            if not snp:
                print(f'{name}: no de-embedded Touchstone file, run combine_extend_snp.py in {data}')
                continue
            shutil.copy(snp[0], os.path.join(SNP, name + '.s3p'))
            with open(os.path.join(d, 'palace.json')) as f:
                j = json.load(f)
            rows.append({'name': name, 'run': run, 'pass': k, 'final': d == out,
                         'unknowns': j['Problem']['DegreesOfFreedom'], 'elements': j['Problem']['MeshElements'],
                         'time_s': round(j['ElapsedTime']['Durations']['Total'], 1),
                         'peak_ram_GB': round(j['PeakMemoryMegabytes']['Total'] / 1024, 2),
                         'error_norm': error_norm(d)})
    with open(os.path.join(HERE, 'runs.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} results in {SNP} and runs.csv')


if __name__ == '__main__':
    main()
