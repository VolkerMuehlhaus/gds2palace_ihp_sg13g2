"""Palace runs on hpz2, one at a time. remote.py run <name> ...  |  status  |  collect <name> ...
A queue waits for the one before it (flock), so at most 16 processes run on the machine from this study."""
import os
import subprocess
import sys
import tarfile
import time
import io

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("STUDY_HOST", "hpz2")   # hpz2 or ryzen9
FOLDER = "claude/inductor_frame_margin"


def ssh(command, **kwargs):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=15", HOST, command], text=True, capture_output=True, **kwargs)


def run(names):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name in names:
            tar.add(os.path.join(HERE, "palace_model", f"{name}_data"), arcname=f"{name}_data")
    subprocess.run(["ssh", HOST, f"mkdir -p ~/{FOLDER} && tar -xf - -C ~/{FOLDER}"], input=buffer.getvalue(), check=True)
    script = ["#!/bin/bash", f"cd ~/{FOLDER}", "exec 9>queue.lock", "flock 9"]
    for name in names:
        script.append(f"( cd {name}_data && /usr/bin/time -v ~/scripts/run_palace config.json > palace.log 2> time.log; "
                      f"echo {name} exit $? >> ../progress.log )")
    command = (f"cd ~/{FOLDER} && cat > q_$$.sh && chmod +x q_$$.sh && "
               f"setsid -f ./q_$$.sh > /dev/null 2>&1 < /dev/null")
    # bytes, not text: on Windows text mode writes CRLF and the script then can't start
    subprocess.run(["ssh", HOST, command], input=("\n".join(script) + "\n").encode(), check=True)
    time.sleep(5)
    started = ssh(f"cd ~/{FOLDER} && test -e queue.lock && echo yes").stdout.strip()
    if started != "yes":
        sys.exit("queue did not start: no queue.lock on the host")
    print("queued", len(names))


def status():
    print(ssh(f"cd ~/{FOLDER}; tail -12 progress.log; echo running: $(pgrep -c -x starter)").stdout)


def collect(names):
    paths = " ".join(f"{name}_data/output {name}_data/palace.log {name}_data/time.log" for name in names)
    process = subprocess.run(["ssh", HOST, f"cd ~/{FOLDER} && tar -cf - --exclude='*.vtu' --exclude='*.pvtu' --exclude='paraview' {paths}"],
                             capture_output=True)
    target = os.path.join(HERE, "results")
    os.makedirs(target, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(process.stdout)) as tar:
        tar.extractall(target, filter="data")
    print("collected", len(names), process.stderr.decode()[:300])


if __name__ == "__main__":
    {"run": lambda: run(sys.argv[2:]), "status": status, "collect": lambda: collect(sys.argv[2:])}[sys.argv[1]]()
