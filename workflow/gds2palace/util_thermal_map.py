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

"""Powers from a circuit simulation onto the heat sources of a thermal export.

The KLayout EM Export plug-in's thermal export puts each device on a heat source layer of its own and writes
<name>_thermalmap.json: per heat source its layer, the layout device and, from LVS, the schematic instance name. A
circuit simulation gives the power per instance. This module brings the two together:

    thermal_map = read_thermal_map("amp_thermal_thermalmap.json")
    powers, problems = read_powers("powers.csv")
    layer_power, report = apply_powers(thermal_map, powers)

The powers file has one line per device: name and power in W, separated by a comma, semicolon, tab or spaces.
The name is the schematic instance name as in the LVS netlist (Q1, Xcore.Q1), the name in the LVS database (1,
CORE.1) or the layout device id of the map; case does not matter. The power is a number, SPICE suffixes and a
trailing W allowed (1.5m, 1.5mW, 1.5e-3). Lines starting with # * or ; are comments, a first line without a number
is a header.

Nothing is set silently: heat sources without a power, names that match no heat source or more than one, and
names given twice are all reported, and only the matched heat sources get a power.

Command line, writes the powers into a setupThermal file (.tsimcfg):
    python -m gds2palace.util_thermal_map <name>_thermalmap.json powers.csv <name>.tsimcfg
"""

import json
import re
import sys

MAP_FORMAT = 1
SUFFIXES = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
_LINE = re.compile(r"^(.*?)[\s,;]+([^\s,;]+)\s*$")
_VALUE = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(meg|[tgkmunpf])?w?$")


def read_thermal_map(path):
    """The thermal map written by the thermal export. Raises ValueError if it is not one."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"{path} is not a readable thermal map: {e}")
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError(f"{path} is not a thermal map (no 'sources')")
    if data.get("format", MAP_FORMAT) > MAP_FORMAT:
        raise ValueError(f"{path} has format {data.get('format')}; this gds2palace reads up to {MAP_FORMAT}")
    return data


def parse_power(text):
    """Power in W from '1.5m', '1.5mW', '0.0015', or None."""
    m = _VALUE.match(text.strip().lower())
    if m is None:
        return None
    return float(m.group(1)) * SUFFIXES.get(m.group(2), 1.0)


def read_powers(path):
    """([(name, power in W, line number)], [problem]) from a powers file (see the module docstring)."""
    powers, problems = [], []
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    first = True
    for number, line in enumerate(lines, 1):
        text = line.strip()
        if not text or text[0] in "#*;":
            continue
        m = _LINE.match(text)
        power = parse_power(m.group(2)) if m else None
        if power is None:
            if not first:
                problems.append(f"line {number}: no name and power in W: {text}")
            first = False
            continue
        first = False
        powers.append((m.group(1).strip().strip('"'), power, number))
    return powers, problems


def _keys(source):
    return {str(source[k]).upper() for k in ("instance", "lvs_name", "device") if source.get(k)}


def apply_powers(thermal_map, powers):
    """{heat source layer: power in W} for the powers [(name, W, line)] that match one heat source of thermal_map,
    and a report: assigned [(layer, name, W)], missing (heat sources without a power: instance or device id),
    unknown (names matching no heat source), ambiguous (names matching several), duplicate (heat sources given
    more than one power; none is used), negative (names with a power below 0, used as given)."""
    sources = thermal_map["sources"]
    keys = [_keys(s) for s in sources]
    given = {}
    report = {"assigned": [], "missing": [], "unknown": [], "ambiguous": [], "duplicate": [], "negative": []}
    for name, power, _ in powers:
        matches = [i for i, k in enumerate(keys) if name.upper() in k]
        if not matches:
            report["unknown"].append(name)
        elif len(matches) > 1:
            report["ambiguous"].append(name)
        else:
            given.setdefault(matches[0], []).append((name, power))
        if power < 0:
            report["negative"].append(name)
    layer_power = {}
    for i, source in enumerate(sources):
        label = source.get("instance") or source.get("device")
        if i not in given:
            report["missing"].append(label)
        elif len(given[i]) > 1:
            report["duplicate"].append(label + ": " + ", ".join(n for n, _ in given[i]))
        else:
            name, power = given[i][0]
            layer_power[source["layer"]] = power
            report["assigned"].append((source["layer"], name, power))
    return layer_power, report


def describe_report(report, total):
    """The report of apply_powers as text lines."""
    lines = [f"{len(report['assigned'])} of {total} heat source(s) got a power."]
    for key, text in (("missing", "Heat sources without a power (unchanged)"),
                      ("unknown", "Names that match no heat source"),
                      ("ambiguous", "Names that match several heat sources (give the instance name)"),
                      ("duplicate", "Heat sources with several powers (none used)"),
                      ("negative", "Negative powers (used as given)")):
        if report[key]:
            lines.append(f"{text}: " + ", ".join(report[key]))
    return lines


def apply_to_tsimcfg(path, layer_power):
    """Write the powers into the heat sources of a setupThermal file. Returns the number of sources set."""
    with open(path) as f:
        data = json.load(f)
    count = 0
    for t in data.get("thermal", []):
        if "SOURCE" in str(t.get("type", "")).upper() and t.get("source_layernum") in layer_power:
            t["power"] = layer_power[t["source_layernum"]]
            count += 1
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    return count


def main(argv):
    if len(argv) != 3:
        print("Writes the powers of a circuit simulation into the heat sources of a setupThermal file:\n"
              "    python -m gds2palace.util_thermal_map <name>_thermalmap.json powers.csv <name>.tsimcfg")
        return 2
    map_path, powers_path, tsimcfg_path = argv
    try:
        thermal_map = read_thermal_map(map_path)
    except ValueError as e:
        print(e)
        return 1
    powers, problems = read_powers(powers_path)
    for problem in problems:
        print(problem)
    layer_power, report = apply_powers(thermal_map, powers)
    for line in describe_report(report, len(thermal_map["sources"])):
        print(line)
    print(f"{apply_to_tsimcfg(tsimcfg_path, layer_power)} heat source(s) set in {tsimcfg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
