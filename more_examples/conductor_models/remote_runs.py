"""Run the study models on the simulation machine, one at a time with 16 MPI processes, and collect the results.

  python remote_runs.py push <lane> [folders]   upload the built models (palace_model/*_data) of these folders
                                                 (default: all) and write the lane file <lane>.txt
  python remote_runs.py start <lane>   start that lane (one run at a time, 16 processes: 16 physical cores);
                                       refused while another run is active
  python remote_runs.py queue <after> <lane>   start <lane> once lane <after> has finished
  python remote_runs.py status    show progress.log
  python remote_runs.py collect   copy run.log, palace.json, port-S.csv and config.json of finished runs to results/

The run order is fixed: one structure after another, and within a structure surface, solve_inside,
solve_inside_skin, coarse solve_inside_skin, so that the models of one structure run back to back under the same
thermal conditions. collect replaces the results of an earlier run of the same model.

The first runs of this study (gds2palace 0.9.0, Palace 0.18) are in palace_runs/conductor_models on the simulation
machine; the rerun with gds2palace 0.10.6 and Palace 0.19.0 is in REMOTE below.
"""
import io
import os
import shutil
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = 'hpz2'
REMOTE = 'palace_runs/conductor_models_0106'
SIF = '~/palace_0190_x86_64_v3.sif'
NP = 16
ORDER = ['surface', 'solve_inside_mesh', 'solve_inside_skin_mesh2', 'solve_inside_skin_mesh3', 'solve_inside_skin_mesh5',
         'solve_inside_skin_mesh1']
FOLDERS = ['inductor', 'lines', 'l6n2', 'transformer', 'balun2x1', 'mim_balun', 'dband_balun']


def model_rank(name):
    for k, key in enumerate(ORDER):
        if key in name:
            return k
    raise ValueError(name)


def lane_entries(folders):
    """model folders relative to the remote study folder, in run order"""
    out = []
    for folder in folders:
        pm = os.path.join(HERE, folder, 'palace_model')
        names = [d[:-5] for d in os.listdir(pm) if d.endswith('_data') and os.path.exists(os.path.join(pm, d, 'config.json'))]
        if folder != 'lines':   # only models that still have a script (not leftovers of removed variants)
            names = [n for n in names if os.path.exists(os.path.join(HERE, folder, n + '.py'))]
        if folder == 'lines':   # by width, then model, then length
            key = lambda n: (float(n.split('_')[1][1:].replace('p', '.')), model_rank(n), n)
        else:
            key = lambda n: (model_rank(n), n)
        out += [f'{folder}/palace_model/{n}_data' for n in sorted(names, key=key)]
    return out


def ssh(cmd, **kw):
    return subprocess.run(['ssh', HOST, cmd], capture_output=True, text=True, **kw)


def push(lane, folders):
    entries = lane_entries(folders or FOLDERS)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        for e in entries:
            local = os.path.join(HERE, *e.split('/'))
            for f in os.listdir(local):
                if f.endswith(('.json', '.msh')):
                    t.add(os.path.join(local, f), arcname=f'{e}/{f}')
        text = ('\n'.join(entries) + '\n').encode()
        info = tarfile.TarInfo(lane + '.txt')
        info.size = len(text)
        t.addfile(info, io.BytesIO(text))
    print(f'uploading {len(entries)} models, {buf.tell() / 1e6:.0f} MB')
    r = subprocess.run(['ssh', HOST, f'mkdir -p {REMOTE} && cd {REMOTE} && tar xf -'], input=buf.getvalue(),
                       capture_output=True)
    print(r.stderr.decode() or 'done')
    print('\n'.join(entries))


def start(lane):
    busy = ssh('pgrep -x prterun; pgrep -x palace-x86_64.b').stdout.split()
    if busy:
        sys.exit(f'{HOST} is busy (PIDs {busy}): one run at a time, not started')
    # -n -f: ssh returns at once, the lane keeps running on the remote machine
    subprocess.run(['ssh', '-n', '-f', HOST,
                    f'cd {REMOTE} && setsid nohup ./lane.sh {lane}.txt {NP} {SIF} > /dev/null 2>&1 < /dev/null &'])
    print('lane started')


def queue(after, lane):
    """start <lane> when <after> has finished (its FINISHED line in progress.log), so that only one run is active.
    Waits on the log, not on the process list: a pgrep pattern would also match this waiter's own command line."""
    subprocess.run(['ssh', '-n', '-f', HOST,
                    f'cd {REMOTE} && setsid nohup bash -c "until grep -q \\"LANE {after}.txt FINISHED\\" progress.log; '
                    f'do sleep 20; done; ./lane.sh {lane}.txt {NP} {SIF}" > /dev/null 2>&1 < /dev/null &'])
    print(f'{lane} queued after {after}')


def status():
    print(ssh(f'cat {REMOTE}/progress.log 2>/dev/null; pgrep -x palace-x86_64.b | wc -l').stdout)


def collect():
    out = os.path.join(HERE, 'results')
    r = ssh(f'cd {REMOTE} && for d in $(cat lane*.txt | sort -u); do ls $d/output/*/port-S.csv > /dev/null 2>&1 && '
            'grep -q "^Total" $d/run.log && echo $d; done')
    done = r.stdout.split()
    files = []
    for d in done:
        name = d.rsplit('/', 1)[1][:-5]
        files += [f'{d}/run.log', f'{d}/config.json', f'{d}/output/{name}/port-S.csv', f'{d}/output/{name}/palace.json']
    if files:
        tar = subprocess.run(['ssh', HOST, f'cd {REMOTE} && tar cf - --ignore-failed-read -T -'],
                             input='\n'.join(files).encode(), capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            for m in t.getmembers():
                if m.isfile():
                    name = m.name.split('/')[2][:-5]
                    os.makedirs(os.path.join(out, name), exist_ok=True)
                    open(os.path.join(out, name, os.path.basename(m.name)), 'wb').write(t.extractfile(m).read())
    # port geometry of each model, for the port de-embedding (written by gds2palace next to config.json)
    for folder in FOLDERS:
        pm = os.path.join(HERE, folder, 'palace_model')
        for d in os.listdir(pm) if os.path.isdir(pm) else []:
            src, dst = os.path.join(pm, d, 'port_information.json'), os.path.join(out, d[:-5])
            if os.path.exists(src) and os.path.isdir(dst):
                shutil.copy(src, dst)
    print(f'{len(done)} finished runs on {HOST}, results in {out}')


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'push':
        push(args[0], args[1:])
    elif cmd == 'start':
        start(args[0])
    elif cmd == 'queue':
        queue(args[0], args[1])
    else:
        {'status': status, 'collect': collect}[cmd]()
