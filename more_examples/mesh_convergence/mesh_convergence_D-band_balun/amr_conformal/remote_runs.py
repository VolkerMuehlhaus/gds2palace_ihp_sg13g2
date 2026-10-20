"""Run the study models on the simulation machine, one at a time with 16 MPI processes, and collect the results.

  python remote_runs.py push <lane> <model> [<model> ...]   upload these built models (palace_model/<model>_data)
                                                            and write the lane file <lane>.txt (run order = given order)
  python remote_runs.py start <lane>          start that lane; refused while another Palace run is active
  python remote_runs.py queue <after> <lane>  start <lane> once lane <after> has finished
  python remote_runs.py status                show progress.log
  python remote_runs.py collect [--mesh]      copy run.log, config.json and the Palace output (all AMR iterations,
                                              without field files) of finished runs to palace_model/<model>_data/;
                                              --mesh also copies the saved AMR mesh (needed by make_stage2.py)

lane.sh runs the models of a lane file one after another and skips
models that already have results.
"""
import io
import os
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = 'hpz2'
REMOTE = 'palace_runs/amr_conformal_balun'
SIF = '~/palace_018.sif'
NP = 16
LANE_SH = os.path.join(HERE, 'lane.sh')


def ssh(cmd, **kw):
    return subprocess.run(['ssh', HOST, cmd], capture_output=True, text=True, **kw)


def push(lane, models):
    entries = [f'palace_model/{m}_data' for m in models]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        for e in entries:
            local = os.path.join(HERE, *e.split('/'))
            for f in os.listdir(local):
                if f.endswith(('.json', '.msh', '.mesh', '.meshgz')) and f != 'config_original.json':
                    t.add(os.path.join(local, f), arcname=f'{e}/{f}')
        # lane.sh with LF line ends: a Windows checkout (git autocrlf) has CRLF, which bash can't run
        with open(LANE_SH, 'rb') as f:
            script = f.read().replace(b'\r\n', b'\n')
        for name, data in (('lane.sh', script), (lane + '.txt', ('\n'.join(entries) + '\n').encode())):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
    print(f'uploading {len(entries)} models, {buf.tell() / 1e6:.0f} MB')
    r = subprocess.run(['ssh', HOST, f'mkdir -p {REMOTE} && cd {REMOTE} && tar xf - && chmod +x lane.sh'],
                       input=buf.getvalue(), capture_output=True)
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
    """start <lane> when <after> has finished (its FINISHED line in progress.log). Waits on the log, not on the
    process list: a pgrep pattern would also match this waiter's own command line."""
    subprocess.run(['ssh', '-n', '-f', HOST,
                    f'cd {REMOTE} && setsid nohup bash -c "until grep -q \\"LANE {after}.txt FINISHED\\" progress.log; '
                    f'do sleep 20; done; ./lane.sh {lane}.txt {NP} {SIF}" > /dev/null 2>&1 < /dev/null &'])
    print(f'{lane} queued after {after}')


def status():
    print(ssh(f'cat {REMOTE}/progress.log 2>/dev/null; pgrep -x palace-x86_64.b | wc -l').stdout)


def collect(mesh):
    r = ssh(f'cd {REMOTE} && for d in $(cat lane*.txt | sort -u); do ls $d/output/*/port-S.csv > /dev/null 2>&1 && '
            'grep -q "^Total" $d/run.log && echo $d; done')
    done = r.stdout.split()
    patterns = '-name "*.csv" -o -name "*.json" -o -name "*.s*p"'
    if mesh:
        patterns += ' -o -name "*.mesh" -o -name "*.meshgz"'
    for d in done:
        name = d.rsplit('/', 1)[1][:-5]
        local = os.path.join(HERE, 'palace_model', f'{name}_data')
        tar = subprocess.run(['ssh', HOST, f'cd {REMOTE}/{d} && tar cf - run.log config.json '
                                           f'$(find output -maxdepth 3 -type f \\( {patterns} \\))'],
                             capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(local, filter='data')
        print(f'collected {name}')
    print(f'{len(done)} finished runs on {HOST}')


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'push':
        push(args[0], args[1:])
    elif cmd == 'start':
        start(args[0])
    elif cmd == 'queue':
        queue(args[0], args[1])
    elif cmd == 'collect':
        collect('--mesh' in args)
    else:
        status()
