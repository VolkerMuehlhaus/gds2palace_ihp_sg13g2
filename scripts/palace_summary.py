########################################################################
#
# Copyright 2025 Volker Muehlhaus and IHP PDK Authors
#
# Licensed under the GNU General Public License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.gnu.org/licenses/gpl-3.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################

"""Print a human-readable summary of AWS Palace solver results (palace.json /
error-indicators.csv) for a given <model>_data directory, or recursively for
every such directory found some levels below a given search path. Standalone
CLI equivalent of setupEM's results-summary panel, for workflows that run
gds2palace without the setupEM GUI.
"""

import os
import sys
import json
import csv
import re
import math
import cmath
import argparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from combine_extend_snp import parse_palace_csv

__version__ = "1.0"

_ITERATION_RE = re.compile(r'^iteration(\d+)$')


def _find_output_dir(run_path, model_basename):
    # config.json's Problem.Output is a path relative to config.json's own directory
    config_path = os.path.join(run_path, 'config.json')
    output_rel = None
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            output_rel = config.get('Problem', {}).get('Output')
        except (OSError, json.JSONDecodeError):
            output_rel = None
    if not output_rel:
        output_rel = 'output/' + model_basename
    return os.path.normpath(os.path.join(run_path, output_rel))


def _read_palace_json(dir_path):
    path = os.path.join(dir_path, 'palace.json')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return {
        'duration_s': data.get('ElapsedTime', {}).get('Durations', {}).get('Total'),
        'peak_ram_mb': data.get('PeakMemoryMegabytes', {}).get('Total'),
        'dof': data.get('Problem', {}).get('DegreesOfFreedom'),
        'mesh_elements': data.get('Problem', {}).get('MeshElements'),
    }


def _read_error_indicators(dir_path):
    path = os.path.join(dir_path, 'error-indicators.csv')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8', newline='') as f:
            rows = [row for row in csv.reader(f, skipinitialspace=True) if row]
    except OSError:
        return None
    if len(rows) < 2:
        return None
    headers = [h.strip() for h in rows[0]]
    values = [v.strip() for v in rows[1]]
    fields = dict(zip(headers, values))
    try:
        return {
            'norm': float(fields['Norm']),
            'minimum': float(fields['Minimum']),
            'maximum': float(fields['Maximum']),
            'mean': float(fields['Mean']),
        }
    except (KeyError, ValueError):
        return None


def _read_port_s_data(dir_path):
    """Parse dir_path/port-S.csv (if present) into (freq_list, S_dB_list,
    S_arg_list, num_ports) using combine_extend_snp's CSV parser, or None if
    the file is missing, unfinished, or malformed (e.g. a still-running pass).
    """
    path = os.path.join(dir_path, 'port-S.csv')
    if not os.path.isfile(path):
        return None
    freq, S_dB, S_arg = [], [], []
    try:
        num_ports, _freq_unit = parse_palace_csv(path, freq, S_dB, S_arg)
    except (OSError, ValueError, IndexError, KeyError):
        return None
    if not freq:
        return None
    return freq, S_dB, S_arg, num_ports


def _max_delta_s(prev_data, curr_data):
    """Max |S_curr - S_prev| across all ports and frequencies common to both
    passes, mirroring HFSS's per-pass Max Delta S. Returns None if either
    pass has no port-S data, or the two use different port counts.
    """
    if prev_data is None or curr_data is None:
        return None
    freq_p, dB_p, arg_p, ports_p = prev_data
    freq_c, dB_c, arg_c, ports_c = curr_data
    if ports_p != ports_c:
        return None

    max_delta = 0.0
    found_any = False
    for idx in range(min(len(freq_p), len(freq_c))):
        for key in set(dB_p[idx]) & set(dB_c[idx]):
            try:
                Sp = cmath.rect(10 ** (float(dB_p[idx][key]) / 20.0), math.radians(float(arg_p[idx][key])))
                Sc = cmath.rect(10 ** (float(dB_c[idx][key]) / 20.0), math.radians(float(arg_c[idx][key])))
            except ValueError:
                continue
            found_any = True
            max_delta = max(max_delta, abs(Sc - Sp))
    return max_delta if found_any else None


def _collect_amr_rows(output_dir, iteration_dirs):
    """One row per AMR iteration subfolder, plus the root output_dir as
    'Final': (label, palace_json_dict_or_None, error_indicators_dict_or_None,
    max_delta_s_vs_previous_row_or_None).
    """
    dirs_in_order = list(iteration_dirs) + [output_dir]
    labels = [os.path.basename(d) for d in iteration_dirs] + ["Final"]

    rows = []
    prev_port_s = None
    for label, d in zip(labels, dirs_in_order):
        summary = _read_palace_json(d)
        errors = _read_error_indicators(d)
        port_s = _read_port_s_data(d)
        delta_s = _max_delta_s(prev_port_s, port_s)
        rows.append((label, summary, errors, delta_s))
        prev_port_s = port_s
    return rows


def _find_run_dirs(search_root):
    """Recursively locate every directory at or below search_root that directly
    contains a config.json (a gds2palace/Palace run directory). Does not descend
    further once such a directory is found, since a run's own output tree never
    contains a nested config.json - this also keeps the walk from wasting time
    inside large mesh/output data trees.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(search_root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        if 'config.json' in filenames:
            found.append(dirpath)
            dirnames[:] = []  # don't descend into this run's own output tree
    found.sort()
    return found


def _derive_model_basename(run_path):
    dirname = os.path.basename(os.path.normpath(run_path))
    return dirname[:-len('_data')] if dirname.endswith('_data') else dirname


def _list_iteration_dirs(output_dir):
    if not os.path.isdir(output_dir):
        return []
    found = []
    for name in os.listdir(output_dir):
        match = _ITERATION_RE.match(name)
        full_path = os.path.join(output_dir, name)
        if match and os.path.isdir(full_path):
            found.append((int(match.group(1)), full_path))
    found.sort(key=lambda item: item[0])
    return [full_path for _, full_path in found]


def _format_duration(seconds):
    if seconds is None:
        return 'n/a'
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def _format_ram(mb):
    if mb is None:
        return 'n/a'
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def _format_int(n):
    return 'n/a' if n is None else f"{n:,}"


def _format_sci(x):
    return 'n/a' if x is None else f"{x:.3e}"


def _format_delta(x):
    return 'n/a' if x is None else f"{x:.4f}"


def _save_convergence_summary(run_path, summary_text):
    """Save the AMR summary table alongside the run's config.json /
    port_information.json, so it's available on disk without re-running the
    simulation or scrolling back through this script's console output.
    """
    try:
        with open(os.path.join(run_path, "mesh_convergence_summary.txt"), "w", encoding="utf-8") as f:
            f.write(summary_text + "\n")
    except OSError:
        pass


def build_results_summary(run_path, model_basename):
    """Return (text, rows) for the Palace results found under run_path: a
    formatted multi-line summary (or an explanatory message if nothing is
    there yet), and the AMR rows from _collect_amr_rows() if this run used
    adaptive mesh refinement, else None.
    """
    output_dir = _find_output_dir(run_path, model_basename)
    if not os.path.isdir(output_dir):
        return (f"No Palace results found yet (expected output directory: {output_dir}) "
                 "-- has the simulation finished?"), None

    iteration_dirs = _list_iteration_dirs(output_dir)

    if not iteration_dirs:
        summary = _read_palace_json(output_dir)
        errors = _read_error_indicators(output_dir)
        if summary is None:
            return (f"No palace.json found yet in {output_dir} "
                     "-- has the simulation finished?"), None
        lines = [
            f"=== Simulation results: {model_basename} ===",
            f"Degrees of freedom : {_format_int(summary['dof'])}",
            f"Mesh elements      : {_format_int(summary['mesh_elements'])}",
            f"Simulation time    : {_format_duration(summary['duration_s'])}",
            f"Peak RAM           : {_format_ram(summary['peak_ram_mb'])}",
        ]
        if errors:
            lines.append(
                f"Error indicator    : Norm={_format_sci(errors['norm'])}  "
                f"Max={_format_sci(errors['maximum'])}  Mean={_format_sci(errors['mean'])}"
            )
        lines.append("=" * 40)
        return "\n".join(lines), None

    # Adaptive mesh refinement: one row per iteration subfolder, plus the root as "Final"
    rows = _collect_amr_rows(output_dir, iteration_dirs)

    headers = ["Iteration", "DOF", "Mesh elems", "Error Norm", "Error Max", "Error Mean",
               "Max dS", "Time", "Peak RAM"]
    table_rows = []
    for label, summary, errors, delta_s in rows:
        summary = summary or {}
        errors = errors or {}
        table_rows.append([
            label,
            _format_int(summary.get('dof')),
            _format_int(summary.get('mesh_elements')),
            _format_sci(errors.get('norm')),
            _format_sci(errors.get('maximum')),
            _format_sci(errors.get('mean')),
            _format_delta(delta_s),
            _format_duration(summary.get('duration_s')),
            _format_ram(summary.get('peak_ram_mb')),
        ])

    widths = [max(len(headers[i]), *(len(r[i]) for r in table_rows)) for i in range(len(headers))]

    def fmt_row(cells):
        return " | ".join(
            cell.ljust(widths[i]) if i == 0 else cell.rjust(widths[i])
            for i, cell in enumerate(cells)
        )

    lines = [f"=== Simulation results: {model_basename} (adaptive mesh refinement) ==="]
    header_line = fmt_row(headers)
    lines.append(header_line)
    lines.append("-+-".join("-" * w for w in widths))
    for row in table_rows:
        lines.append(fmt_row(row))
    lines.append("=" * len(header_line))
    summary_text = "\n".join(lines)
    _save_convergence_summary(run_path, summary_text)
    return summary_text, rows


def plot_convergence(rows, model_basename, out_path):
    """Render an HFSS-style convergence chart (error-indicator norm and max
    delta-S vs. AMR iteration, log-y) for the rows built by
    _collect_amr_rows(), and save it to out_path. Returns out_path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    indices = list(range(len(rows)))
    labels = [label for label, _summary, _errors, _delta_s in rows]

    norm_x, norm_y = [], []
    for i, (_label, _summary, errors, _delta_s) in zip(indices, rows):
        if errors and errors.get('norm') is not None:
            norm_x.append(i)
            norm_y.append(errors['norm'])

    delta_x, delta_y = [], []
    for i, (_label, _summary, _errors, delta_s) in zip(indices, rows):
        if delta_s is not None:
            delta_x.append(i)
            delta_y.append(delta_s)

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.set_xlabel("AMR iteration")
    ax1.set_xticks(indices)
    ax1.set_xticklabels(labels, rotation=45, ha='right')

    ax1.set_ylabel("Error indicator norm", color='tab:blue')
    ax1.set_yscale("log")
    line1, = ax1.plot(norm_x, norm_y, marker='o', color='tab:blue', label='Error norm')
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel("Max |ΔS|", color='tab:red')
    ax2.set_yscale("log")
    line2, = ax2.plot(delta_x, delta_y, marker='s', color='tab:red', label='Max ΔS')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    ax1.legend(handles=[line1, line2], loc='upper right')
    fig.suptitle(f"AMR convergence: {model_basename}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# --------------------------
#   main
# --------------------------


def print_run_config(parser, args):
    """Print the full set of available commandline options and how to use
    them, followed by the value actually used for each on this run - so a
    user never has to guess what a run did after the fact."""
    print(parser.format_help())
    print("Resolved configuration for this run:")
    for name, value in sorted(vars(args).items()):
        print(f"  {name} = {value}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Print a summary of AWS Palace solver results (degrees of "
                     "freedom, mesh size, runtime, peak RAM, adaptive-mesh-"
                     "refinement error indicators). Recursively searches "
                     "search_path for every gds2palace run directory (one "
                     "containing config.json) and prints a summary for each "
                     "one found."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "search_path", nargs="?", default=os.getcwd(),
        help="directory to search, recursively, for Palace run directories "
             "(i.e. <model>_data directories containing config.json). Can "
             "point directly at a single run directory, or at a parent "
             "directory containing many (default: current directory)"
    )
    parser.add_argument(
        "--model-basename", default=None,
        help="model base name override, used only when exactly one run "
             "directory is found (ignored, with a note printed, when "
             "multiple runs are found - each then uses its own name). Also "
             "used to locate the fallback output directory "
             "output/<model_basename> when config.json is missing "
             "(default: derived from the run directory name by stripping a "
             "trailing '_data' suffix)"
    )
    parser.add_argument(
        "--plot", action="store_true",
        help="for each run that used adaptive mesh refinement, also render a "
             "convergence chart (error-indicator norm and max delta-S vs. "
             "AMR iteration, HFSS-style) and save it as convergence.png in "
             "that run's directory (requires matplotlib)"
    )
    args = parser.parse_args()

    search_path = os.path.abspath(args.search_path)
    run_dirs = _find_run_dirs(search_path)

    if not run_dirs:
        # no config.json anywhere below search_path - fall back to treating
        # search_path itself as the run directory, so this still works for
        # the output/<model_basename> fallback case and for "no results yet"
        run_dirs = [search_path]

    if len(run_dirs) == 1:
        model_basename = args.model_basename or _derive_model_basename(run_dirs[0])
        basenames = [model_basename]
        args.model_basename = model_basename  # show the resolved value, not None
    else:
        if args.model_basename:
            print(f"NOTE: ignoring --model-basename '{args.model_basename}' -- "
                  f"{len(run_dirs)} run directories found, each uses its own name.\n")
        basenames = [_derive_model_basename(d) for d in run_dirs]

    print_run_config(parser, args)

    if len(run_dirs) > 1:
        print(f"Found {len(run_dirs)} Palace run directories under {search_path}:")
        for d in run_dirs:
            print(f"  {d}")
        print()

    any_incomplete = False
    for run_path, model_basename in zip(run_dirs, basenames):
        if len(run_dirs) > 1:
            print(f"----- {run_path} -----")
        summary, rows = build_results_summary(run_path, model_basename)
        print(summary)
        print()
        if summary.startswith("No Palace results found yet") or summary.startswith("No palace.json found yet"):
            any_incomplete = True

        if args.plot:
            if rows:
                out_path = os.path.join(run_path, "convergence.png")
                plot_convergence(rows, model_basename, out_path)
                print(f"Convergence plot saved to: {out_path}\n")
            else:
                print(f"--plot requested but no AMR iterations found for {model_basename}, skipping.\n")

    sys.exit(1 if any_incomplete else 0)


if __name__ == "__main__":
    main()
