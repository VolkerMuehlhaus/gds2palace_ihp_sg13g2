#!/bin/bash
# Run every model listed in a lane file, one after another, skipping models that already have results.
# usage (on the simulation machine, from ~/palace_runs/amr_conformal_balun):
#   setsid nohup ./lane.sh <lane file> <cores> <container> > /dev/null 2>&1 < /dev/null &
#   e.g. hpz2:   ./lane.sh hpz2_A.txt 8 ~/palace_018.sif
#        ryzen9: ./lane.sh ryzen9_A.txt 8 ~/palace_018_v3b.sif   (generic x86_64_v3 build, see README)
# Lane files list model folders relative to this directory, e.g. palace_model/ind_N1_d27_w2p01_s2p1_data.
# A model counts as finished when output/*/port-S.csv exists, so a lane can be stopped and restarted at any time,
# and a lane file can contain models that another lane already finished.
# Keep the total number of MPI processes on a machine at or below its 16 physical cores (e.g. two lanes of 8).
# "< /dev/null" on palace is required: mpirun otherwise reads the rest of the lane file from stdin.
LANE=$1; NP=$2; SIF=$3
ROOT=$(cd "$(dirname "$0")" && pwd)
export OMP_NUM_THREADS=1
while read -r d; do
  [ -z "$d" ] && continue
  cd "$ROOT/$d" || { echo "$d MISSING $(date +%T)" >> "$ROOT/progress.log"; continue; }
  if ls output/*/port-S.csv > /dev/null 2>&1; then cd "$ROOT"; continue; fi
  t0=$(date +%s)
  apptainer exec "$SIF" palace -np "$NP" config.json > run.log 2>&1 < /dev/null
  if ls output/*/port-S.csv > /dev/null 2>&1; then status=done; else status=FAILED; fi
  echo "$d $status $(( $(date +%s) - t0 )) s $(hostname) $(date +%T)" >> "$ROOT/progress.log"
  cd "$ROOT"
done < "$ROOT/$LANE"
echo "LANE $LANE FINISHED $(hostname) $(date +%T)" >> "$ROOT/progress.log"
