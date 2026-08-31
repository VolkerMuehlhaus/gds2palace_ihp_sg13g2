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
error-indicators.csv) for a given <model>_data directory. Standalone CLI
equivalent of setupEM's results-summary panel, for workflows that run
gds2palace without the setupEM GUI.
"""

import os
import sys
import json
import csv
import re
import argparse

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


def build_results_summary(run_path, model_basename):
    """Return a formatted multi-line summary of Palace results found under run_path,
    or an explanatory message if nothing is there yet.
    """
    output_dir = _find_output_dir(run_path, model_basename)
    if not os.path.isdir(output_dir):
        return (f"No Palace results found yet (expected output directory: {output_dir}) "
                 "-- has the simulation finished?")

    iteration_dirs = _list_iteration_dirs(output_dir)

    if not iteration_dirs:
        summary = _read_palace_json(output_dir)
        errors = _read_error_indicators(output_dir)
        if summary is None:
            return (f"No palace.json found yet in {output_dir} "
                     "-- has the simulation finished?")
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
        return "\n".join(lines)

    # Adaptive mesh refinement: one row per iteration subfolder, plus the root as "Final"
    rows = [(os.path.basename(it_dir), _read_palace_json(it_dir), _read_error_indicators(it_dir))
            for it_dir in iteration_dirs]
    rows.append(("Final", _read_palace_json(output_dir), _read_error_indicators(output_dir)))

    headers = ["Iteration", "DOF", "Mesh elems", "Error Norm", "Error Max", "Error Mean", "Time", "Peak RAM"]
    table_rows = []
    for label, summary, errors in rows:
        summary = summary or {}
        errors = errors or {}
        table_rows.append([
            label,
            _format_int(summary.get('dof')),
            _format_int(summary.get('mesh_elements')),
            _format_sci(errors.get('norm')),
            _format_sci(errors.get('maximum')),
            _format_sci(errors.get('mean')),
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
    return "\n".join(lines)


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
                     "refinement error indicators) found in a gds2palace "
                     "<model>_data directory."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "run_path", nargs="?", default=os.getcwd(),
        help="path to the <model>_data directory containing config.json "
             "(default: current directory)"
    )
    parser.add_argument(
        "--model-basename", default=None,
        help="model base name, used to locate the fallback output directory "
             "output/<model_basename> when config.json is missing, and shown "
             "in the summary header (default: derived from the run_path "
             "directory name by stripping a trailing '_data' suffix)"
    )
    args = parser.parse_args()

    run_path = os.path.abspath(args.run_path)
    model_basename = args.model_basename
    if not model_basename:
        dirname = os.path.basename(os.path.normpath(run_path))
        model_basename = dirname[:-len('_data')] if dirname.endswith('_data') else dirname
        args.model_basename = model_basename  # show the resolved value, not None

    print_run_config(parser, args)

    summary = build_results_summary(run_path, model_basename)
    print(summary)

    if summary.startswith("No Palace results found yet") or summary.startswith("No palace.json found yet"):
        sys.exit(1)


if __name__ == "__main__":
    main()
