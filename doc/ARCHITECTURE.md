# gds2palace Architecture — a reference for AI agents

This document exists to orient an AI coding agent quickly and *accurately* in this repository:
what gds2palace actually is, what it is not, exactly how a model script talks to it, exactly what
happens when you "run" a model (including the parts that live outside this repo entirely), and a
worked analysis of the most structurally interesting example in the tree (inductor synthesis).

It complements, rather than replaces, `doc/userguide_md_format/gds2palace_workflow_userguide.md`
(the human-facing user guide — more screenshots, more narrative, less "trace the exact function
calls"). Where the two disagree, trust the source code citations in this document; they were
verified directly against the files at the time of writing, not inferred from the user guide's
prose.

**Repo root** for every path below: `D:\github-claude\gds2palace_ihp_sg13g2\` (GitHub:
`VolkerMuehlhaus/gds2palace_ihp_sg13g2`, upstream of the `volkermuehlhaus-claude` fork this
workspace develops under).

---

## 1. What gds2palace is, in one paragraph

gds2palace is a pure Python toolkit that turns a GDSII layout plus an XML "stackup" file
(metal/dielectric layer definitions, materials, via rules — specific to the IHP SG13G2 open-source
RFIC PDK) into the input files for **AWS Palace**, a 3D FEM electromagnetic solver, or
alternatively for **Elmer FEM**, a different open-source FEM solver. A model script — a short,
hand-written (or AI-written, or setupEM-GUI-generated) Python file — imports `gds2palace`,
describes a few simulation settings and a handful of ports, and calls one function
(`simulation_setup.create_palace(...)` or `create_elmer(...)`). That call runs `gmsh` under the
hood to build 3D geometry and mesh it, then writes out the solver's native input files. **Neither
Palace nor Elmer is part of this package** — see §5.

---

## 2. Package layout — `workflow/gds2palace/`

| File | Approx. size | Responsibility |
|---|---|---|
| `__init__.py` | 27 lines | Defines the entire public import surface (below) |
| `util_stackup_reader.py` | ~1550 lines | Parses the XML technology stackup file |
| `util_gds_reader.py` | ~600 lines | Parses the GDSII layout into polygon objects |
| `util_simulation_setup.py` | **2694 lines** | The core engine: ports, gmsh geometry/mesh construction, Palace `config.json` writer, Elmer `.sif` writer |
| `util_elmer.py` | ~600 lines | Elmer-specific file writers — internal, never imported directly by model scripts |
| `util_utilities.py` | 146 lines | Path/filename helpers, the `run_sim`/`run_elmer` wrapper-script generators |

`workflow/gds2palace/__init__.py` (full file, verified):

```python
from . import util_stackup_reader as stackup_reader
from . import util_gds_reader as gds_reader
from . import util_utilities as utilities
from . import util_simulation_setup as simulation_setup

__version__ = "0.4.1"   # version of gds2palace
```

So `from gds2palace import *` gives a model script exactly **four names**:
`stackup_reader`, `gds_reader`, `utilities`, `simulation_setup`. `util_elmer` is *not*
re-exported — it's an internal dependency of `util_simulation_setup.py`
(`from . import util_elmer` at `util_simulation_setup.py:30`), never called directly from a model
script.

**PyPI package name is `gds2palace`, importable as `gds2palace`** — but note the *directory* it
lives in inside this repo is `workflow/gds2palace/`, not the repo root; when reading example
scripts you'll often see `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))`
before `from gds2palace import *` — that's for running a script directly against the in-repo source
without installing the package (see `pyproject.toml`'s `[tool.setuptools.packages.find]`, which
publishes `workflow/gds2palace/` as the top-level `gds2palace` package).

---

## 3. Stackup XML format, `stackupEditor`, and agent-driven stackup generation

Every model script needs an XML "stackup" file — layer stack, materials, via rules — read via
`stackup_reader.read_substrate()` (§4 step 4). This section covers the file format itself, the GUI
tool for editing it, and — most relevant to an agent with no GUI — **how to generate or edit one
programmatically**, using the exact functions the GUI itself is built on.

### 3.1 — File format

Format spec: `doc/XML_stackup_format/XML_stackup_format.md` (this repo); related:
`doc/XML_stackup_format/derived_layers.md`, `doc/XML_stackup_format/evolution_of_stackup_file_format.md`.
Top-level structure:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Stackup schemaVersion="2.0">
  <Variables>...</Variables>        <!-- optional, must be the FIRST child -->
  <Materials>...</Materials>
  <ELayers LengthUnit="um">
    <Dielectrics>...</Dielectrics>
    <Layers>...</Layers>
    <DerivedLayers>...</DerivedLayers>  <!-- optional -->
  </ELayers>
  <Tables>...</Tables>               <!-- optional, thermal conductivity tables -->
</Stackup>
```

Smallest real example in the repo, `workflow/pcb_ro4003.xml` (full file, verified):
```xml
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
  <Stackup schemaVersion="2.0">
    <Materials>
      <Material Name="Copper" Type="Conductor" Permittivity="1" DielectricLossTangent="0" Conductivity="3.3e7" Color="00ff00"/>
      <Material Name="RO4003" Type="Dielectric" Permittivity="3.38" DielectricLossTangent="0.0022" Conductivity="0" Color="01e0ff"/>
      <Material Name="AIR" Type="Dielectric" Permittivity="1.0" DielectricLossTangent="0.0" Conductivity="0" Color="d0d0d0"/>
    </Materials>
    <ELayers LengthUnit="um">
      <Dielectrics>
        <Dielectric Name="RO4003" Material="RO4003" Thickness="510" />
      </Dielectrics>
      <Layers>
        <Substrate Offset="0"/>
        <Layer Name="Bottom" Type="Conductor" Zmin="-17" Zmax="0" Material="Copper" Layer="1" />
        <Layer Name="Top" Type="Conductor" Zmin="510" Zmax="527" Material="Copper" Layer="10" />
      </Layers>
    </ELayers>
  </Stackup>
```

**`<Materials>`** — one `<Material>` per material: `Name`, `Type` (`Conductor`/`Dielectric`/
`Semiconductor`/`Resistor`), `Permittivity`, `DielectricLossTangent`, `Conductivity`, `Rs`, plus
thermal-only `Density`/`ThermalConductivity`/`ThermalConductivityTable`, and a `Color` (hex, used
by the stackup preview).

**`<Dielectrics>`** — the vertical dielectric stack, independent of GDSII, listed top-to-bottom.
Position is resolved by priority: (1) explicit `Zmin`+`Zmax`, (2) Reference-relative
(`Reference="<other Dielectric Name>"` + optional `ReferenceEdge`, default `Top`; own `Zmin`
defaults `0`, `Zmax` defaults `Zmin+Thickness`), (3) legacy implicit stacking by `Thickness` alone.

**`<Layers>`** — drawn, GDSII-sourced layers. `Type` ∈ `conductor`/`via`/`dielectric`/`sheet` —
maps 1:1 to `util_stackup_reader.py`'s `metal_layer.is_metal`/`is_via`/`is_dielectric`/`is_sheet`
flags (`util_stackup_reader.py:909-974`, see also §4's canonical-pattern walkthrough); `Zmin==Zmax`
forces `sheet` regardless of the stated `Type`. `<Substrate Offset="...">` shifts every Layer's z
by a fixed amount — mutually exclusive with any `Reference`-based Layer in the same file.

**Reference-relative positioning** (`schemaVersion="3.0"+`) replaces hand-recomputed absolute
z-values and the single global `Substrate Offset` fudge factor with a `Reference`/`ReferenceEdge`
chain, resolved in dependency order regardless of file order — so a whole stack no longer needs
re-deriving by hand whenever one Dielectric's thickness changes.

**`<DerivedLayers>`** (`schemaVersion="3.0"+`) — computes a new GDSII layer number from existing
ones via boolean ops `AND`/`OR`/`XOR`/`NOT` (≥2 operands, folded pairwise) or `SIZE` (1 operand,
resize by `Oversize`). Operands may chain off other derived layers (topologically sorted). Full
detail: `doc/XML_stackup_format/derived_layers.md`.

**`<Variables>`** (`schemaVersion="3.1"+`, current `SUPPORTED_SCHEMA_VERSION`,
`util_stackup_reader.py:66`) — must be the first child of `<Stackup>`. Any attribute value anywhere
in the file starting with `=` is an expression (`+ - * / **`, parens, references to other Variables
by name), resolved in dependency order with circular-reference detection:
```xml
<Variables>
  <Variable Name="cu_conductivity" Value="21640000.0" />
  <Variable Name="via_top" Value="=metal_thickness + via_thickness" />
</Variables>
```
`stackup_reader.read_substrate(XML_filename, variable_overrides={...})` lets a model script
override a named Variable at run time without editing the XML — the mechanism setupEM's "Override
stackup Variables" grid feeds into.

### 3.2 — `stackupEditor`: what it is, and what it's built on

`stackupEditor` is a PySide6 GUI (`setupEM/src/setupEM/stackupEditor.py`, `StackupEditorWindow`,
console script `stackupEditor = "setupEM.stackupEditor:main"`, in the sibling `setupEM` repo) for
editing stackup XML files without hand-editing — Variables, Materials, Dielectric stack, Layers,
Derived Layers, and thermal Tables, each as an editable grid, plus a live cross-section preview.

**The important architectural fact for an agent: the GUI holds no separate, richer domain model of
its own.** Its single source of truth is a plain `xml.etree.ElementTree` (`self.tree`),
loaded/created via `stackup_writer.load_stackup_tree(filename)` / `stackup_writer.new_stackup_tree()`.
Every tab is a generic `ElementTableEditor` widget parameterized with plain `stackup_writer`
functions as callbacks, e.g.:
```python
add_fn=lambda root, **attrs: stackup_writer.add_material(root, **attrs),
remove_fn=stackup_writer.remove_material,
type_choices=list(stackup_writer.VALID_MATERIAL_TYPES),
```
So editing a row in the GUI just calls the same `stackup_writer.add_material()`/`remove_material()`/
etc. an agent would call directly. There is no intermediate GUI-only object an agent needs to
reconstruct.

### 3.3 — `stackup_writer.py`: the actual, GUI-independent XML editing API

`setupEM/src/setupEM/stackup_writer.py` (1347 lines) is a **standalone module with zero Qt/GUI
dependency** — its only imports are `ast`, `xml.etree.ElementTree`, and
`from gds2palace import stackup_reader` (itself pure stdlib). Its own docstring states the intent
directly: it's deliberately kept separate from `util_stackup_reader.py` because *"the reader turns
XML into the read-only object model ... used by the rest of gds2palace, while this module is for
tools that need to load a file, edit it ..., and write it back out ... while leaving any parts of
the file they don't understand (e.g. XML comments) completely untouched."*

**This means: an AI agent can generate or edit a stackup XML file by importing `stackup_writer`
directly and calling it — no GUI, no Qt event loop, no `QApplication` — exactly the functions
`stackupEditor` itself calls.**

Full public API (function names/signatures verified directly against source):
```python
load_stackup_tree(filename)                                   # -> ElementTree, comment-preserving parse
new_stackup_tree(length_unit="um", schema_version="2.0")       # -> ElementTree, minimal empty <Stackup>
save_stackup_tree(tree, filename)                               # writes to disk, self-corrects schemaVersion

get_materials_element(root) / get_dielectrics_element(root) / get_layers_element(root)
get_substrate_offset_element(root) / get_derived_layers_element(root, create=False)
get_variables_element(root, create=False) / get_tables_element(root, create=False)

add_material(root, **attrs)  / remove_material(root, element)
add_dielectric(root, index=None, **attrs)  / remove_dielectric(root, element)
move_dielectric(root, element, direction)      # direction: -1 up / +1 down
add_layer(root, **attrs)  / remove_layer(root, element)
set_substrate_offset(root, value)              # value None/0 removes the <Substrate> element
add_derived_layer(root, **attrs)  / remove_derived_layer(root, element)
get_operand_layers(element) / set_operands(element, layer_numbers)
add_variable(root, **attrs)  / remove_variable(root, element)
add_table(root, **attrs)  / remove_table(root, element)
add_point(table_element, **attrs)  / remove_point(table_element, element)

validate_stackup(root)          # -> list[str] of problems, [] if OK
required_schema_version(root)   # -> "2.0"/"3.0"/"3.1", the minimum actually needed by file content
stamp_header_comments(root, app_name, description="")
get_file_description(root)      # -> str
```
`add_*`/`remove_*` take/return plain `Element` objects; keyword arguments become XML attributes
directly (`None`/`""` values are skipped). `VALID_MATERIAL_TYPES`, `VALID_LAYER_TYPES`,
`VALID_DERIVED_OPERATIONS` module-level tuples give the exact allowed values for each `Type`/
`Operation` field.

**Comment preservation is real, not just a GUI-editor claim**: `load_stackup_tree()` uses a custom
comment-preserving parser (`ET.TreeBuilder(insert_comments=True)`), so hand-written
`<!-- comments -->` in a file survive an agent's load→edit→save round-trip untouched — including
any `<Tables>` content, which the writer's own logic never touches at all.

**Worked example** — generating the `pcb_ro4003.xml` file above from scratch, using nothing but
`stackup_writer`:
```python
from setupEM import stackup_writer

tree = stackup_writer.new_stackup_tree(length_unit="um", schema_version="2.0")
root = tree.getroot()

stackup_writer.add_material(root, Name="Copper", Type="Conductor",
                             Permittivity="1", DielectricLossTangent="0",
                             Conductivity="3.3e7", Color="00ff00")
stackup_writer.add_material(root, Name="RO4003", Type="Dielectric",
                             Permittivity="3.38", DielectricLossTangent="0.0022",
                             Conductivity="0", Color="01e0ff")

stackup_writer.add_dielectric(root, Name="RO4003", Material="RO4003", Thickness="510")

stackup_writer.set_substrate_offset(root, 0)
stackup_writer.add_layer(root, Name="Bottom", Type="conductor",
                          Zmin="-17", Zmax="0", Material="Copper", Layer="1")
stackup_writer.add_layer(root, Name="Top", Type="conductor",
                          Zmin="510", Zmax="527", Material="Copper", Layer="10")

errors = stackup_writer.validate_stackup(root)
if errors:
    raise SystemExit("\n".join(errors))

stackup_writer.stamp_header_comments(root, app_name="agent-script",
                                      description="Generated programmatically")
stackup_writer.save_stackup_tree(tree, "pcb_ro4003_generated.xml")
```
(`stackup_writer` is a plain submodule of the installed `setupEM` package — not re-exported from
`setupEM`'s own top-level `__init__.py` (which only exports `main`), so
`import setupEM.stackup_writer as stackup_writer` / `from setupEM import stackup_writer` both work,
but `from setupEM import *` will not surface it.)

**Cross-repo note**: `stackup_writer.py` lives in the `setupEM` repo, not this one —
`gds2palace_ihp_sg13g2` has no writer of its own (`util_stackup_reader.py` only reads). Using it
requires `setupEM` installed alongside `gds2palace` (`setupEM`'s own `pyproject.toml` already
depends on `gds2palace>=0.4.0`, never the reverse — confirmed no `setupEM` reference anywhere in
this repo's `pyproject.toml`).

### 3.4 — Does an agent-generated file actually round-trip through gds2palace's reader?

Reasonably reliably, and not just by construction — **`stackup_writer.save_stackup_tree()` actively
exercises gds2palace's own `stackup_reader.parse_substrate()`** as part of every save, to resolve
sort order for Layers (by resolved `Zmin`) and Table points (by resolved `Temperature`), and
`required_schema_version()`/`validate_stackup()` run their own independent checks beforehand. So a
file that passes `validate_stackup(root)` cleanly and saves without error has already been parsed
once by the real reader logic before it ever reaches disk. The one caveat: the save-time sort steps
silently skip their cosmetic reordering (not fail the whole save) if `parse_substrate()` raises —
so a clean `validate_stackup()` result plus a successful save is strong, but not
absolutely 100%-exhaustive, evidence the file will read back correctly. **The definitive check
remains calling `gds2palace.stackup_reader.read_substrate()` on the generated file directly** and
confirming no exception.

---

## 4. The canonical model-script pattern

Traced end-to-end from `workflow/palace_rfcmim.py` (a hand-written RF MIM capacitor model — chosen
as representative because it's not one of the more elaborate synthesis/sweep scripts) and
cross-checked against `workflow/line_simple_viaport.py`. Every model script in this repo — hand
written, setupEM-generated, or the inductor synthesis scripts (§12) — follows this same sequence.

```python
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'gds2palace')))
from gds2palace import *

# --- 1. path/output-directory bootstrap ---
script_path    = utilities.get_script_path(__file__)
model_basename = utilities.get_basename(__file__)
sim_path       = utilities.create_sim_path(script_path, model_basename)

# --- 2. settings dict (plain dict, see §6 for the full key reference) ---
settings = {}
settings['unit']              = 1e-6
settings['margin']            = 50
settings['fstart']            = 1e9
settings['fstop']             = 20e9
settings['fstep']             = 1e9
settings['refined_cellsize']  = 2

XML_filename = "SG13G2_nosub.xml"
gds_filename = "my_layout.gds"

# --- 3. ports ---
simulation_ports = simulation_setup.all_simulation_ports()
simulation_ports.add_port(simulation_setup.simulation_port(
    portnumber=1, voltage=1, port_Z0=50, source_layernum=201,
    from_layername='Metal1', to_layername='TopMetal1', direction='z'))
simulation_ports.add_port(simulation_setup.simulation_port(
    portnumber=2, voltage=1, port_Z0=50, source_layernum=202,
    from_layername='Metal1', to_layername='Metal5', direction='z'))

# --- 4. read the stackup ---
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)

# --- 5. build the layer list to extract, and read the GDSII ---
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0],
    metals_list=metals_list, preprocess=True, merge_polygon_size=0)

# --- 6. stuff everything the engine needs into settings ---
settings['simulation_ports'] = simulation_ports
settings['materials_list']   = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list']      = metals_list
settings['layernumbers']     = layernumbers
settings['allpolygons']      = allpolygons
settings['sim_path']         = sim_path
settings['model_basename']   = model_basename

# --- 7. build the model (writes config.json + mesh + port_information.json) ---
excite_ports = simulation_ports.all_active_excitations()
config_name, data_dir = simulation_setup.create_palace(excite_ports, settings)

# --- 8. write the convenience run script into sim_path ---
utilities.create_run_script(sim_path)
```

### What each call actually does

- **`utilities.create_sim_path(script_path, model_basename, dirname='palace_model')`**
  (`util_utilities.py:54-83`) builds `<script_dir>/palace_model/<model_basename>_data/` and
  creates it (`os.makedirs`). On Windows, if the resulting path would exceed 200 characters, or if
  directory creation fails for any other reason, it silently falls back to a directory under the
  system temp dir instead (`util_utilities.py:67-81`) — worth knowing if a generated model's
  output ends up somewhere unexpected on a Windows box with a deeply-nested repo path.

- **`simulation_setup.simulation_port(...)`** (`util_simulation_setup.py:33-78`) validates, at
  construction time, that you've specified either a **via port** (`direction` contains `z`/`Z`,
  plus `from_layername` + `to_layername`) or an **in-plane port** (`direction` contains `x`/`y`,
  plus `target_layername`) — anything else prints an error and calls `exit(1)` immediately
  (`:60-68`). There is no gentler failure mode here; a malformed port definition kills the whole
  script at construction time, before any geometry or meshing work happens.

- **`all_simulation_ports.all_active_excitations()`** (`:160-172`) returns only the ports whose
  `abs(voltage) > 1e-6` — a `voltage=0` port is *defined* (its geometry still gets built and it
  still appears as a matrix row/column) but never *excited*. This is the mechanism used throughout
  the repo to cheaply simulate "just this one path" of a larger multi-port structure — see the
  ATTENTION callout in §8.

- **`stackup_reader.read_substrate(XML_filename, variable_overrides=None)`**
  (`util_stackup_reader.py:1456-1482`) parses the XML with a comment-preserving `ElementTree`
  parser, validates `schemaVersion`, and returns exactly the 3-tuple
  `(materials_list, dielectrics_list, metals_list)`. `metals_list` also carries
  `.derived_layers` for the boolean-operation "derived layer" feature (§3.1). `variable_overrides`
  is a dict of `{variable_name: value}` used to override a `<Variables>`-declared value from Python
  without editing the XML file — this is exactly the mechanism setupEM's "Override stackup
  Variables" grid feeds into.

- **`gds_reader.read_gds(filename, layerlist, purposelist, metals_list, preprocess=False,
  merge_polygon_size=0, mirror=False, offset_x=0, offset_y=0, gds_boundary_layers=[],
  layernumber_offset=0, cellname="", derived_layers=None)`** (`util_gds_reader.py:502-524`) opens
  the GDS via `gdspy.GdsLibrary`, flattens the top-level cell, and for each requested layer number
  extracts layer/datatype polygons matching `purposelist`. Via-array polygons get merged when
  `metal.is_via` and `merge_polygon_size > 0` (`merge_via_array`, `:596-597`). **Known
  documentation drift worth flagging**: the `preprocess` argument is currently a no-op that just
  prints a message (docstring/comment at `:511`/`:534-536` says polygon-cutout handling is
  "obsolete, cutouts are handled safely downstream after flattening") — but
  `doc/userguide_md_format/gds2palace_workflow_userguide.md:321` still describes it as an active
  preprocessing step. If you're an agent reasoning from the user guide alone, don't assume
  `preprocess_gds=True/False` changes behavior; check the current source before relying on it.

- **`simulation_setup.create_palace(excite_ports, settings)`** (`:1054-1066`) is a thin wrapper —
  it just calls `create_model(excite_ports, settings)`. Palace is the *default* mode.
  `create_elmer(excite_ports, settings)` (`:1015-1029`) sets `settings['elmer']=True` then calls
  the same `create_model()`. `create_elmer_thermal(settings)` (`:1032-1051`, no `excite_ports` —
  thermal has no EM ports) sets `settings['elmer']=True, settings['elmer_thermal']=True` and dummy
  `fstart=fstop=1e9` (mesh-only frequencies). **All three funnel into one 1620-line function,
  `create_model()`** (`:1071-2693`) — this is the actual engine. In order, it:
  1. Pulls every setting out of the `settings` dict with defaults via a local
     `get_optional_setting(settings, key, default)` closure (`:1082-1084`) — unrecognized/missing
     optional keys fall back to sane defaults rather than raising.
  2. `gmsh.initialize()`, creates a fresh gmsh model (`:1276-1288`).
  3. `add_metal_volumes(...)` (`:1339`) — turns each drawn polygon into a gmsh 3D volume or 2D
     surface depending on the corresponding XML `<Layer>` type (via / dielectric-brick / sheet /
     planar metal).
  4. `add_dielectrics(...)` (`:1352`) — builds the stackup dielectric boxes and, unless doing
     thermal, an outer airbox sized by `margin`/`air_around`.
  5. Boolean-cuts metal out of dielectric (`gmsh.model.occ.cut`, `:1388`), then
     `gmsh.model.occ.fragment(...)` (`:1404`) to conformally stitch everything together.
  6. `add_ports(...)` — builds port 2D-sheet surfaces and writes `port_information.json` (port
     number, `Z0`, direction, geometry, in microns) into `sim_path` (`:1770-1781`) — this file is
     gds2palace's own metadata, consumed later by the Touchstone-conversion script (§9), never by
     Palace itself.
  7. Assigns gmsh physical groups for every conductor/dielectric/boundary entity.
  8. **Palace path** (`if not elmer:`, `:2171-2174`): writes `config.json` — a nested dict with
     `Problem` (`Type`, `Verbose`, `Output` = `"output/<model_basename>"`), `Model` (mesh filename,
     `L0`, AMR `Refinement` block), `Solver` (linear-solver params, `Order`, `Device: "CPU"`,
     `Driven.Samples` frequency list, `AdaptiveTol`), `Domains.Materials` (keyed by numeric gmsh
     physical-group `Attributes`), and `Boundaries` (`Conductivity`, `LumpedPort`, optionally
     `Impedance`/`Absorbing`/`PEC`/`PMC`) — built at `:1800-2167`.
  9. **Elmer path** (`if elmer:`, `:2181-2397`): builds equivalent `Elmer_*` structures and calls
     `util_elmer.write_elmer_frequencies/write_elmer_physics_file/write_elmer_thermal_file/
     write_case_and_solver_files`, plus writes `ELMERSOLVER_STARTINFO`.
  10. Mesh-size fields from `refined_cellsize`/`refined_cellsize_override`/`meshsize_max`/
      `cells_per_wavelength` (~`:2400-2640`), optional gmsh GUI preview (`gmsh.fltk.run()`, unless
      `no_gui`/`no_preview`), then `gmsh.model.mesh.generate(3)` and `gmsh.write(msh_name)` —
      **forcing `Mesh.MshFileVersion = 2.2`**, because, per the comment at `:2655`, *"Palace
      requires mesh version 2.2!"*
  11. For Elmer: `util_elmer.convert_mesh_to_elmer(msh_name, ELMER_MPI_THREADS)` (`:2690-2691`)
      converts the `.msh` to Elmer's native mesh format via the external `ElmerGrid` tool.
  12. Returns `(config_name, data_dir)` — `data_dir` is literally the string
      `'output/' + model_basename` (`:1229`), a relative path baked into `config.json`'s
      `Problem.Output`. **Palace itself creates that `output/` directory when it runs** — gds2palace
      never creates it.

- **`utilities.create_run_script(sim_path)`** (`util_utilities.py:86-102`) writes a convenience
  wrapper — see §5.4 for exact content and why it exists.

### Concrete files a Palace run produces (verified against a real generated directory)

`<script_dir>/palace_model/<model_basename>_data/`:
```
config.json                    # Palace's solver-control file (written by gds2palace)
<model_basename>.msh           # gmsh mesh, forced to format version 2.2 (written by gds2palace)
port_information.json          # gds2palace's own port metadata (written by gds2palace)
run_sim                        # convenience wrapper (written by gds2palace, see §5.4)
mesh_convergence_summary.txt   # only if adaptive_mesh_iterations > 0
output/                        # created BY PALACE ITSELF when it runs — empty/absent until then
```
For Elmer:
```
case.sif  ELMERSOLVER_STARTINFO  first-order.sif  frequencies.dat  physics.sif
quadratic-direct.sif  quadratic-iterative.sif  run_elmer  port_information.json
<model_basename>.msh   mesh/    # ElmerGrid-converted mesh partition directory
```

---

## 5. "Palace itself is not included" — what that means concretely

### 5.1 — Confirmed: not a Python dependency

`pyproject.toml`:
```toml
[project]
name = "gds2palace"
...
dependencies = [
    "gdspy>1.6.0",
    "gmsh",
]
```
Only `gdspy` and `gmsh` are pip dependencies. **No `palace`, no MPI bindings, nothing
solver-related.** `pip install gds2palace` gives you the model-file *generator*, nothing that can
actually run an FEM solve.

### 5.2 — What this package does vs. what it explicitly does not do

- `README.md:26`: *"It creates model files for the AWS Palace FEM solver, which must be installed
  separately, as described in chapter 'Installing Palace'."*
- `README.md:63`: *"The gds2palace workflow does not change, it only creates the input files for
  Palace and does not care how you installed Palace, or on what platform you run the actual Palace
  simulation from these model files."*

So concretely: gds2palace's job stops at producing `<model>.msh` + `config.json` (+
`port_information.json`) inside `palace_model/<name>_data/`. Actually **running** the FEM solve —
the compute-heavy, MPI-parallel, compiled C++/MFEM binary that reads that `.msh` + `config.json`
and produces raw S-parameters — is entirely external to this repo and this package.

### 5.3 — What a user or agent must install/provide separately

Two documented installation paths for the Palace binary, **both Linux-only**
(`README.md:25`: *"This workflow is designed for Linux systems"*):

1. **Apptainer/Singularity container** (the author's own recommended path):
   `apptainer pull palace_016.sif oras://ghcr.io/volkermuehlhaus/palace_016:latest`
   (`README.md:52`). Documented in `doc/Installing_Palace_using_Apptainer.pdf` (present in the
   repo; PDF, not inlined as markdown anywhere).
2. **Build from source via the Spack package manager** — `doc/Installing_Palace_using_Spack.pdf`.

Either way, the repo's own reference launcher, **`scripts/run_palace`** (full file, 2 lines):
```bash
#!/bin/bash
apptainer exec ~/palace.sif palace -np 8 $1
```
This runs the `palace` binary *inside* a container image at `~/palace.sif`, with Palace's own
`-np 8` flag telling it to partition the simulation domain across 8 MPI processes, and `$1` (the
first CLI argument, expected to be `config.json`) passed straight through.

**`scripts/README.md` is explicit that this is just the author's own dev setup, not a
requirement**: *"If you prefer to install and run Palace in a different way, no problem! The
gds2palace workflow creates the input files for Palace, and it is entirely your choice how you run
the simulator with these model files, local or on a sophisticated HPC cluster."*

There's also **`scripts/run_palace_remote`**, meant to be renamed to `run_palace` in place of the
local version: it `scp`s the entire model output directory to a remote Linux machine, `ssh`es in
and runs that machine's own `run_sim` (see §5.4 below) there, then `scp`s the resulting `output/`
directory back — i.e. Palace execution is fully decoupled from wherever the Python model-generation
step ran (you can generate model files on Windows/macOS and simulate on a remote Linux box).

### 5.4 — The generated per-model `run_sim` wrapper (distinct from `scripts/run_palace`)

`utilities.create_run_script(sim_path)` (called at the end of every model script, §4 step 8) writes
this exact content into `<sim_path>/run_sim` (`util_utilities.py:91-93`):
```bash
#!/bin/bash
run_palace config.json
combine_snp
```
(written with forced Unix line endings even on Windows, and `chmod 0o755`'d only when actually
running on Linux — `util_utilities.py:96-102`).

**The relationship between the two:**
- `run_sim` is generated **fresh into every model's own output directory** by gds2palace. It
  contains no simulator-specific configuration — it's purely "solve this model, then convert its
  results," and it calls `run_palace`/`combine_snp` as bare commands, relying on `$PATH`.
- `run_palace` (and `combine_snp`) are **general-purpose, hand-configured-once-per-machine**
  scripts that must exist somewhere on `PATH` (`scripts/README.md`: *"Include the script folder to
  your PATH"*). They decide *how* Palace actually launches on this particular machine (which
  container image, how many cores, or — via the renamed `run_palace_remote` — dispatch to a
  different machine entirely).

**An agent generating a new model should call `utilities.create_run_script(sim_path)` exactly as
existing scripts do, and should assume a working `run_palace` + `combine_snp` already exist on
`PATH` in the target execution environment — it should not try to reimplement Palace invocation
logic itself.**

Some model scripts additionally offer an in-Python auto-run toggle right after `create_palace()`:
```python
start_simulation = False
run_command = ['./run_sim']
...
if start_simulation:
    os.chdir(sim_path)
    subprocess.run(run_command, shell=True)
```
— i.e. the model script itself can `cd` into the freshly-created output directory and shell out to
`./run_sim` immediately after generating it.

**Elmer equivalent**: `utilities.create_elmer_run_script(sim_path, settings)` writes `run_elmer`
into `sim_path`, either:
```bash
#!/bin/bash
ElmerSolver
combine_snp
```
(single-threaded, when `settings['ELMER_MPI_THREADS']` is 1 or unset) or:
```bash
#!/bin/bash
mpirun -np 8 ElmerSolver case.sif
combine_snp
```
(multi-threaded — the exact `-np N` value comes from `util_elmer.get_ELMER_MPI_THREADS(settings)`).

---

## 6. `settings` dict — the full key reference

`settings` is a **plain Python dict**, not a class, passed straight into
`simulation_setup.create_palace(excite_ports, settings)` / `create_elmer(...)`. This table is
reproduced from `doc/userguide_md_format/gds2palace_workflow_userguide.md:333-362` (verified
against the source, e.g. `get_optional_setting` defaults in `util_simulation_setup.py:1082-1224`).

**Always required:**

| Key | Meaning |
|---|---|
| `unit` | Unit of values in mesh, typically `1e-6` (micron) |
| `margin` | Oversize of dielectrics from the drawing's bounding box, in the xy plane |
| `fstart`, `fstop`, `fstep` | Frequency sweep, in Hz. Not every step is necessarily EM-simulated, due to the adaptive frequency sweep |
| `refined_cellsize` | Target mesh size at polygon edges, in `unit` |

**Optional — discrete frequencies in addition to / instead of the sweep:**

| Key | Meaning |
|---|---|
| `fpoint` | List of discrete frequencies, e.g. `[10e9, 15e9]` |
| `fdump` | Like `fpoint`, but Palace also writes a field dump for Paraview at these frequencies — see §10 |

**Optional — everything else:**

| Key | Default | Meaning |
|---|---|---|
| `cells_per_wavelength` | 10 | Calculated at the highest frequency; must be ≥10 |
| `meshsize_max` | 70 | Maximum mesh size limit, on top of `cells_per_wavelength` |
| `refined_cellsize_override` | `[]` | Per-layer override, e.g. `[['Metal3', 10], ['Metal2', 2]]`. Only conductor/sheet layers produce the boundary curves this applies to — a via or dielectric layer name (or any typo/nonexistent name) is a plain dict-key miss inside `create_model()`, silently ignored with no error (`util_simulation_setup.py`'s `refined_cellsize_override_dict` lookup, fed only by `boundary_line_tags_dict`, which vias/dielectrics never populate). setupEM's own "Advanced..." mesh-override dialog restricts its layer picker to valid conductor/sheet layers for exactly this reason. |
| `boundary` | `['ABC']*6` | 6 values for xmin/xmax/ymin/ymax/zmin/zmax: `ABC`/`PML`, `PEC`, or `PMC` |
| `air_around` | same as `margin` | Single value, or a list of 6 `[xmin,xmax,ymin,ymax,zmin,zmax]` values. `0` is allowed on any side (e.g. a backside ground plane flush with the simulation boundary, no wasted air layer) |
| `order` | 2 | FEM basis-function order (2 = accurate; 1 = quick/dirty) — see §7 for what this actually does to accuracy |
| `substrate_refinement` | `False` | Extra mesh refinement into the substrate |
| `adaptive_sweep` | `True` | Enable Palace's adaptive frequency sweep |
| `adaptive_mesh_iterations` | 0 | AMR iterations — often unnecessary with a fine initial mesh |
| `save_adaptive_mesh` | `False` | Save the AMR-iteration mesh for reuse |
| `save_gmsh_unrolled` | `False` | Also save the unmeshed gmsh geometry, for inspection |
| `z_thickness_factor` | 1 | Factor on metal-thickness for conductor side walls (relevant when skin depth exceeds metal thickness) |
| `no_gui` | `False` | Don't show the gmsh UI — for unattended/scripted runs |
| `no_preview` | `False` | Skip the unmeshed-geometry preview, go straight to showing the meshed model |

**Not user-facing settings, but required in the dict before calling `create_palace`/`create_elmer`**
(built during steps 4-6 of §4, not typed by hand): `simulation_ports`, `materials_list`,
`dielectrics_list`, `metals_list`, `layernumbers`, `allpolygons`, `sim_path`, `model_basename`.

---

## 7. FEM order and what it does to accuracy

`settings['order']` selects the polynomial order of the finite-element basis functions Palace uses
within each mesh cell (tetrahedron): 1 (linear), 2 (quadratic, the default), or 3 (cubic). Enforced
in code (`util_simulation_setup.py:1156-1159`): any value outside `1-3` prints a warning and falls
back to `order=2`. It maps directly to `config.json`'s `Solver.Order` field (`:1897`).

**What raising the order actually buys you**: a higher-order basis function can represent field
variation *within a single mesh cell* more accurately (more degrees of freedom per cell), so a
coarser mesh (larger `refined_cellsize`) can reach the same accuracy as a much finer mesh at a
lower order. Conversely, order=1 needs a denser mesh to resolve the same field distribution
accurately — this is the classic FEM p-refinement (raise polynomial order) vs. h-refinement (refine
the mesh) trade-off.

The user guide documents a real head-to-head comparison for exactly this trade-off
(`doc/userguide_md_format/gds2palace_workflow_userguide.md:430-485`, an 880 µm long / 15 µm-wide
TopMetal2-over-Metal1 microstrip line testcase), simulated four different ways:

| `refined_cellsize` | `order` | Simulation time | Degrees of freedom (DOF) |
|---|---|---|---|
| 2 µm | 1 | 64 s | 321,999 |
| 5 µm | 2 | 282 s | 699,658 |
| **2 µm** | **2 (default)** | **733 s** | **1,640,126** |
| 5 µm | 3 | 1967 s | 1,982,661 |

Findings from that comparison, quoted/paraphrased from the user guide:
- **order=1 is a clear outlier** — visibly different S11/S21 magnitude and phase from every
  higher-order configuration, regardless of mesh density. Treat order=1 as "quick/dirty" only,
  never for a final result.
- **`refined_cellsize=5, order=3` reproduces the `refined_cellsize=2, order=2` baseline almost
  exactly** (S11 and S21 magnitude/phase visually identical) — confirming a higher basis-function
  order really can substitute for a finer mesh.
- But in this case that substitution was **not a good trade**: it took *more* DOF and nearly 3×
  the simulation time (1967 s vs. 733 s) to match the accuracy the default
  (`refined_cellsize=2, order=2`) already gave more cheaply. The guide's own conclusion:
  *"refined_cellsize=2, order=2 is the best choice for accurate data... at less simulation time."*

**Practical guidance for an agent choosing these settings**: don't reach for `order=3` as a first
move to improve accuracy — try tightening `refined_cellsize` at the default `order=2` first, and
only escalate to `order=3` if a documented convergence check (e.g. via `adaptive_mesh_iterations`,
or a manual before/after comparison like the one above) shows it's actually needed. `order=1`
should be reserved for fast exploratory sweeps where some visible error is acceptable — this is
exactly how the inductor-synthesis examples in §12 use it (`order=1` for a broad coarse sweep
across dozens of candidates, `order=2` only for the finalists).

**Elmer note**: Elmer's EM solver only supports `order` 1 or 2 — "other values fall back to the
order-1 solver recipe" (`doc/userguide_md_format/gds2palace_workflow_userguide.md:827`). `order=3`
is Palace-only.

---

## 8. Ports

Ports are geometry-driven: **drawn as polygons on special GDSII layers** (conventionally 201 and
up) that are not part of the real IHP layer table, then mapped by `simulation_port(...)` to real
technology layers via `from_layername`/`to_layername` (vertical/via port) or `target_layername`
(in-plane port), plus a `direction` (`x`/`y`/`z`, case-insensitive per `util_simulation_setup.py`'s
`Z in self.direction.upper()`-style checks).

**Two structural quirks worth knowing:**

1. **`voltage` doesn't mean voltage to Palace** — Palace itself doesn't support the `voltage`
   parameter; it only supports polarity reversal by flipping port direction. This workflow instead
   *repurposes* `voltage` as an excitation on/off switch: **`voltage=0` means "define this port's
   geometry, but don't excite it."** `all_simulation_ports.all_active_excitations()` filters out
   any port with `abs(voltage) <= 1e-6` before it's passed to `create_palace(...)`.
2. **Palace runs one excitation at a time, sequentially.** To get a full S-matrix you must define
   *every* port with a nonzero voltage — Palace then simulates each excitation, one after another,
   automatically. **If any port is left at `voltage=0`, its row in the S-parameter output is
   entirely absent (later padded with zeros by the Touchstone converter, §9)** — this is a
   deliberate, useful trick for cheaply simulating just one signal path of a larger multi-port
   structure, not a bug.

Port shape requirement: ports are **2D-sheet lumped ports**. For a vertical (via) port, draw a
zero-width box in GDSII (a line, effectively) — a finite-area box still works, but the port sheet
is placed along its centerline. Composite ports (multiple EM ports grouped into one logical port)
are **not supported**.

---

## 9. From raw Palace output to Touchstone `.snp`

### 9.1 — `port-S.csv` is Palace's own native output, not something gds2palace writes

gds2palace's only involvement in Palace's output is setting `config.json`'s
`Problem.Output = "output/<model_basename>"` (`util_simulation_setup.py:1802-1807`) — a relative
path telling Palace where to write its own results. **Palace itself** creates that `output/`
directory and writes `port-S.csv` (and other files) into it when it actually runs — the CSV's
column-header convention (`|S[i][j]|`/`arg(S[i][j])`, `(dB)`/`(deg.)` suffixes) is Palace's native
format, not anything gds2palace defines.

gds2palace does separately write its own metadata file, `port_information.json`, directly into
`sim_path` (one level up from Palace's `output/<model>/` folder) — port number, `Z0`, direction,
geometry (length/width/position), and `unit`. This is *not* consumed by Palace; it's read back only
by the Touchstone-conversion step below, for the `Z0` header value and for optional de-embedding.

### 9.2 — `combine_snp` → `combine_extend_snp.py`

`scripts/combine_snp` (full file, the thin invocation wrapper):
```bash
#!/bin/bash
~/venv/palace/bin/python ~/scripts/combine_extend_snp.py
```
Intentionally hardcoded to a particular venv/script path — `scripts/README.md` explicitly says
"Please modify this as required for your environment." It takes **no arguments**: it relies on
`combine_extend_snp.py`'s own `os.getcwd()`-based recursive directory walk, so it must be run from
within (or above) the directory tree holding the Palace/Elmer output — which is exactly what
`run_sim`/`run_elmer` do, since they run it right after the solve, from `sim_path`.

**What `combine_extend_snp.py` actually does, traced through its real logic** (full source at
`scripts/combine_extend_snp.py`, ~480 lines):

1. **Discovery**: recursively walks the current directory tree, collecting every file literally
   named `port-S.csv` (Palace) or `scalar_results.names` (Elmer) — a brute-force scan, which is
   exactly why it tolerates Palace's AMR `iterationN/` subfolder nesting (one AMR iteration's
   result sits one directory level deeper than the final result).
2. **Per found file**: walks *upward* from the file's directory, up to 4 levels, looking for a
   sibling `port_information.json`. If found: extracts each port's `Z0` into a Touchstone header
   value (supports mixed port impedances as a space-separated list), and reads an optional
   `"name"` field used as a filename fallback — needed because Elmer's native output directory is
   always literally called `mesh`. If not found: defaults `Z0` to `"50"` and later prints a
   warning.
3. **Parsing**: `parse_palace_csv()` for `port-S.csv` (strips Palace's CSV formatting, enumerates
   which `S[i][j]` columns are actually present — since only excited ports produce data) or
   `parse_elmer_results()` for `scalar_results.names`+its paired data file (Elmer's "coupling
   matrix" `cmf`/`cmf im` columns, converted from angular frequency in rad/s to GHz).
4. **Assembling Touchstone rows**: for 2-port results specifically, swaps to `S[j][i]` ordering to
   match Touchstone's traditional `S11 S21 S12 S22` convention (any other port count uses natural
   row-major `S[i][j]` order). Any `(i,j)` pair with no data (an un-excited port, per §8) is padded
   with `0.0`/`0.0` — this is exactly the "missing rows padded with zeros" behavior the user guide
   documents.
5. **Writing**: `<parentname>.s<N>p` (e.g. `mymodel.s2p`), written by hand (not via scikit-rf's
   writer) as a header line `#  {freq_unit} S DB R {Z0_string}` followed by one
   whitespace-separated data line per frequency.
6. **DC extrapolation** (`extrapolate_to_DC()`): only if the Touchstone file has more than 20
   frequency points *and* its lowest frequency is ≤1 GHz — Palace's frequency-domain solve cannot
   go all the way to 0 Hz — this step re-reads the file via `skrf.Network` and calls scikit-rf's
   `extrapolate_to_dc(points=None, dc_sparam=None, kind='cubic', coords='polar')`, writing the
   result as `<basename>_dc.s<N>p`.
7. **Port de-embedding** (`port_deembedding()`, marked **experimental** in `scripts/README.md`):
   if `port_information.json` gave port `length`/`width`, computes a parasitic series inductance
   per port using a flat-ribbon-inductor formula credited to F.E. Terman's *Radio Engineers
   Handbook* (1945):
   ```python
   def flat_strip_inductance(length, width, thickness, unit):
       return 2e-7 * length * unit * (
           math.log(2*length/(width+thickness)) + 0.5 + 0.2235*(width+thickness)/length
       )
   ```
   (`thickness=0` always — "Palace ports are 2D sheets with no thickness"), then cascades a
   *negative* series inductor of that value onto each port of the network (via scikit-rf's
   `media.inductor(...)` + `connect(...)`), writing the result as `<basename>_deembedded.s<N>p`.
   Applied to both the plain and (if present) the `_dc`-extrapolated file.

### 9.3 — End-to-end summary

```
model script
  → simulation_setup.create_palace(excite_ports, settings)
      writes config.json (Problem.Output = "output/<model_basename>") + <model>.msh + port_information.json
      into <script_dir>/palace_model/<model_basename>_data/
  → utilities.create_run_script(sim_path)
      writes run_sim: "run_palace config.json" then "combine_snp"

./run_sim  (or the model script's own start_simulation=True auto-run)
  → run_palace config.json     [machine-specific, on PATH — repo's own dev version:
                                 apptainer exec ~/palace.sif palace -np 8 config.json, Linux-only]
      Palace writes output/<model_basename>/port-S.csv (+ other native files)
  → combine_snp                [machine-specific, on PATH — repo's own dev version:
                                 ~/venv/palace/bin/python ~/scripts/combine_extend_snp.py]
      finds port-S.csv, cross-references port_information.json for Z0/geometry,
      writes <model_basename>.s<N>p, then optionally _dc.s<N>p and _deembedded.s<N>p
```

---

## 10. Creating field dumps

In addition to S-parameters, Palace can write a full 3D field-solution dump (viewable in ParaView)
at specific frequencies, via `settings['fdump']` — a list of frequencies in Hz, same shape as
`fpoint` (§6):
```python
settings["fdump"] = [15e9]   # save a field dump at 15 GHz
```
(real usage: `workflow/palace_L2n0.py:84`; likewise `workflow/palace_butlermatrix_dump93.py:84`
with `[93e9]`).

Mechanically, this is threaded straight into `config.json`'s frequency sweep list
(`util_simulation_setup.py:1870-1880`): each `fdump` frequency becomes its own `"Type": "Point"`
entry in `Solver.Driven.Samples`, with **`"SaveStep": 1`** — as opposed to a plain `fpoint`
discrete frequency, which gets `"SaveStep": 0`. `SaveStep: 1` is the flag that tells Palace to
write field-solution output at that sample; gds2palace itself does not configure a separate output
directory or file format for this — it's entirely Palace's own native field-dump mechanism,
written under the same `Problem.Output` directory as the raw `port-S.csv` results (§9.1).

Real usage from the user guide (`workflow/palace_L2n0.py`, an octagon inductor with via ports): with
`settings["fdump"] = [15e9]`, opening Palace's resulting field-dump output in ParaView shows the
current density distribution across the structure at 15 GHz — useful for sanity-checking where
current is actually flowing (e.g. confirming skin-effect crowding, or spotting an unintended
current path), not something derivable from S-parameters alone.

**When to use it**: `fdump` is for visual/qualitative inspection of one or a few specific
frequencies, not for production S-parameter extraction — don't add it to every frequency in a
sweep (that multiplies Palace's output size and runtime for no benefit). Pick one or two
frequencies of specific interest (a resonance, a suspected problem frequency), the way both real
examples above do.

---

## 11. Elmer FEM — the alternative solver path

Elmer FEM (https://www.elmerfem.org/) is a **second, independent, also-not-included** open-source
FEM solver — a genuine alternative back end to Palace, not a pre/post-processing helper of it.
`doc/userguide_md_format/gds2palace_workflow_userguide.md:785` is explicit: *"Elmer FEM is not
distributed with gds2palace and must be installed separately... gds2palace needs to find two Elmer
command-line tools: `ElmerGrid` (mesh conversion) and `ElmerSolver` (the solver itself)."* On
Windows, gds2palace looks for `%ELMER_HOME%\bin\ElmerGrid.exe`; on Linux/macOS, both tools must be
on `PATH`.

Choosing Elmer instead of Palace is a **one-line change at the very end of an otherwise identical
model script** — same `settings`, same ports, same `stackup_reader`/`gds_reader` calls:
```python
# Palace:
config_name, data_dir = simulation_setup.create_palace(excite_ports, settings)
utilities.create_run_script(sim_path)
# Elmer:
config_name, data_dir = simulation_setup.create_elmer(excite_ports, settings)
utilities.create_elmer_run_script(sim_path, settings)
```
Both funnel into the same `create_model()` engine (§4), gated by `settings['elmer']`. Documented
behavioral differences: Elmer's EM solver always solves *all* defined ports in one run (no
per-excitation skip trick — though `voltage=0` ports are still just not excited/counted), has no
adaptive-frequency-sweep equivalent, and (as of this writing) lacks sheet-resistor and composite-port
support.

There's a third mode, `create_elmer_thermal(settings)` — Elmer-only, no Palace equivalent,
steady-state thermal (temperature) simulation using `heatsource`/`constanttemp` objects instead of
EM ports. Out of scope for this document (see the user guide's "Using gds2palace with Elmer FEM for
thermal simulation" chapter), but worth knowing it exists if you see `elmer_thermal` in the
codebase.

---

## 12. Case study: the inductor synthesis examples

There are **two** inductor-synthesis examples in `more_examples/`:

1. `inductor_synthesis_no_external_library/synthesize_ihp_inductor_v3.py`
2. `inductor_synthesis_using_pclab_library/synthesize_inductor_v11.py`

**This chapter primarily analyzes #1**, which its own sibling README (in example #2's directory)
cross-references as the more illustrative, self-contained example of gds2palace usage: *"For
inductor synthesis in IHP SG13G2 without need for an external geometry library, see this
example."* Example #2 delegates all geometry generation to a vendored, modified copy of the
third-party [pcLab](https://github.com/dgrujic/pcLab) library — it's really a demo of "gds2palace +
pcLab integration," not of gds2palace's own API surface. The differences are summarized in §12.5.

### 12.1 — What's actually being "synthesized"

**Geometry, not just EM verification of a pre-drawn part.** The script draws a symmetric
octagonal spiral inductor directly to GDSII in Python (via `gdspy` primitives), for a whole grid of
candidate `(turns N, width w, spacing s)` combinations, computing each candidate's required outer
diameter `D` from a closed-form equation. gds2palace is used purely as the **EM solver backend
inside an optimization loop** — called once per candidate geometry, many times per run — not to
generate geometry itself.

The example's own README states its 8-step "principle of operation" plainly:

1. Determine candidate implementations via closed-form equations (required diameter for target L),
   filtering out ones that are geometrically invalid or exceed a maximum diameter.
2. Create GDSII layouts for every candidate (including ports + ground return).
3. Run a **fast, low-order** FEM sweep over all candidates via gds2palace.
4. Evaluate the top-N candidates by Q factor at the target frequency, and re-tune each toward the
   target L.
5. After a fixed number of re-tune iterations, pick the single best candidate and run a **full,
   wideband, high-order** FEM sweep on it.
6. Plot L and Q of that final candidate.
7. Generate a final "production" GDSII with all the extra IHP SG13G2 OPDK layout features required
   for a real PDK cell (no simulation-only geometry).

### 12.2 — The optimization loop, precisely

```
closed-form estimate (Wheeler's equation) for D, per (N, w, s) combo
  → draw candidate GDSII (with EM ports + ground-return frame)
  → gds2palace EM sim, order=1 (fast/coarse)     [one create_palace() call per candidate]
  → read back .s2p via skrf.Network, compute differential L/Q at target frequency
  → keep the best-Q candidates, rescale D by sqrt(Ltarget / L_measured)
  → redraw, gds2palace EM sim, order=2 (accurate)   [repeated a *fixed* number of iterations —
                                                       not until convergence]
  → pick the single winner
  → gds2palace EM sim, wideband, order=2 (final)
  → regenerate GDSII with production OPDK decoration layers, no ports/ground frame
```

**This is grid search + a fixed-point rescaling loop, not a real optimizer** — there is no
`scipy.optimize` anywhere in either script. An agent asked to "improve convergence" here should
understand this existing pattern before reaching for a different optimization algorithm.

### 12.3 — How gds2palace is actually called (per candidate)

The per-candidate model-creation function (`create_simulation_model()`) is a direct instance of
§4's canonical pattern, just wrapped in a function and invoked in a loop:

```python
sim_path = utilities.create_sim_path(script_path, model_basename)
simulation_ports = simulation_setup.all_simulation_ports()
for portnumber in range(1, portcount+1):
    simulation_ports.add_port(simulation_setup.simulation_port(
        portnumber=portnumber, voltage=1, port_Z0=50,
        source_layernum=200+portnumber,
        from_layername=ground_layer_name, to_layername=port_layer_name,
        direction='z'))

layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0],
    metals_list=metals_list, preprocess=settings['preprocess_gds'],
    merge_polygon_size=settings['merge_polygon_size'])

settings['simulation_ports'] = simulation_ports
settings['materials_list']   = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list']      = metals_list
settings['layernumbers']     = layernumbers
settings['allpolygons']      = allpolygons
settings['sim_path']         = sim_path
settings['model_basename']   = model_basename

excite_ports = simulation_ports.all_active_excitations()
config_name, data_dir = simulation_setup.create_palace(excite_ports, settings)
return config_name, data_dir
```

**Batch execution**: rather than running each candidate's Palace solve immediately, the script
collects `config_name`s across a whole sweep phase and writes a single shell script
(`simulate_all`) that `cd`s into each candidate's data directory and runs `run_palace <config.json>`
for all of them **sequentially** — explicitly not parallelized, "to avoid asynchronous finish of
simulation jobs" (a comment in the source) — then runs `combine_snp` once at the end and copies all
resulting `.s*p` files back to the script directory. This whole batch is invoked via
`subprocess.run(simulate_script_filename, shell=True)`, gated on `sys.platform.startswith("linux")`
— **this script's Palace-invocation step only actually runs on Linux**, consistent with §5.

**Results are read back entirely outside gds2palace's own API** — using `skrf.Network` directly on
the Touchstone file `combine_snp` produced, then a script-local `get_diff_model()` function converts
the raw 1/2/3-port Z or Y matrix into a scalar differential inductance/resistance/Q (handling the
optional floating center-tap port by nulling it out algebraically). **There is no gds2palace-
provided S-parameter-to-L/Q utility** — every example that needs to "close the loop" from simulation
results back into a design decision re-implements this kind of post-processing itself.

### 12.4 — Non-obvious patterns worth knowing about (for an agent working on similar scripts)

- **No result caching or reuse** — every run deletes prior `palace_model/`, `*.s?p`, `*.gds`
  output and resimulates everything from scratch (`cleanup_old_data=True` by default). No
  memoization of previously-seen `(N,w,s,D)` combinations, even within a single run.
- **Runtime cost is a first-class, explicitly-acknowledged concern**: the initial sweep alone can
  spawn dozens of full 3D-meshed Palace solves (e.g. 2 turn-counts × 8 widths × 4 spacings = up to
  64 combinations, filtered by geometric validity). The script gives the user a 10-second
  `Ctrl+C`-to-abort window before committing to the full batch.
- **FEM order is deliberately varied by phase** — order 1 (fast, less accurate) for the broad
  sweep, bumped to order 2 before the fine-tune loop and kept at 2 for the final wideband run —
  the standard speed/accuracy tradeoff pattern in this codebase (§7).
- **A "faked DC" frequency point** (a low-but-nonzero frequency, e.g. 100 MHz, explicitly commented
  "do not change") stands in for true DC inductance, since a real 0 Hz EM solve is ill-posed — used
  only internally to compute the diameter-rescale factor, not reported to the user.
- **A center-tap port, when present in the drawn geometry, is deliberately excluded from EM
  excitation** during the sweep/fine-tune phases (2-port simulation only, tap left floating) and
  only added back for the final model — meaning intermediate phases produce `.s2p` files while the
  final phase produces `.s3p`. An agent debugging a "file not found" error against one of these
  scripts should check which phase it's in before assuming a bug.
- **Sanity filtering happens before any simulation runs at all**: a candidate whose crossover
  geometry would force physically-invalid via placement, or whose diameter exceeds the configured
  maximum, is dropped from the candidate list before any GDSII is even drawn for it — so the actual
  number of Palace runs in a sweep phase is data-dependent, not simply the full cross-product of
  the configured ranges.
- **The deliverable is a real, PDK-compliant GDSII cell**, not just simulation artifacts: the final
  step regenerates the winning geometry a second time *without* the simulation-only ports/ground
  frame, adding the IHP SG13G2 OPDK decoration layers (`nofill`/`PWell.block`/`NoRCX`/`IND`
  purposes) that a real PDK cell requires, saved with a `final_` prefix alongside its
  `final_`-prefixed verified Touchstone file.

### 12.5 — How the pcLab-based variant (example #2) differs

"No external library" specifically means *no dependency on pcLab* — the SG13G2-specific spiral
drawing, via-array drawing, port/ground-frame drawing, and OPDK decoration that pcLab (plus its
`pin2port`/`ihp_sg13_features` helper modules) would otherwise provide are all reimplemented
directly with `gdspy` primitives in example #1's single script. Concretely, pcLab (vendored at
`more_examples/inductor_synthesis_using_pclab_library/pclab/`) provides:

- A generic technology-rule engine (`pclTech.Technology("SG13G2.tech")`) that geometry classes
  query instead of hard-coded via-rule constants.
- Reusable, technology-agnostic inductor-shape classes (`pclInductor.py`'s `inductorSym`,
  `inductorSymCT`) instead of a single bespoke `symmetric_octa_IHP()` function.
- A generic pin-to-EM-port converter (`pin2port.py`'s `gds_pin2viaport(...)`) that auto-detects
  which side of the bounding box each labeled pin sits on and synthesizes port/frame geometry from
  that, geometrically, rather than example #1's parametric-formula approach.
- A separate, explicit OPDK-decoration post-processing step (`ihp_sg13_features.py`'s
  `gds_add_sg13_features(...)`) rather than example #1's approach of doing decoration inline as
  part of the main drawing function.

The optimization-loop code itself (`create_simulation_model`, `run_models_from_list`,
`get_best_results`, `get_diff_model`, `calc_resize_factor`, the overall sweep→finetune→final flow)
is essentially identical between the two scripts — **the only real difference is in how the
geometry gets drawn**, not in how gds2palace gets used.

---

## 13. Quick checklist — writing a new model script

1. `sys.path.insert(...)` + `from gds2palace import *` (only needed if running against the in-repo
   source rather than an installed package).
2. `utilities.get_script_path/get_basename/create_sim_path` → `sim_path`.
3. Build `settings = {}` with at minimum `unit`, `margin`, `fstart`/`fstop`/`fstep`,
   `refined_cellsize` (§6).
4. Define ports via `simulation_setup.all_simulation_ports()` +
   `simulation_ports.add_port(simulation_setup.simulation_port(...))` (§8) — remember `voltage=0`
   defines-but-doesn't-excite a port.
5. `stackup_reader.read_substrate(XML_filename)` → `materials_list, dielectrics_list, metals_list`
   (§3 covers the file format and how to generate/edit one programmatically via `stackup_writer`).
6. `layernumbers = metals_list.getlayernumbers(); layernumbers.extend(simulation_ports.portlayers)`.
7. `gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, ...)`
   → `allpolygons`.
8. Stuff `simulation_ports`, `materials_list`, `dielectrics_list`, `metals_list`, `layernumbers`,
   `allpolygons`, `sim_path`, `model_basename` into `settings`.
9. `excite_ports = simulation_ports.all_active_excitations()`, then
   `simulation_setup.create_palace(excite_ports, settings)` (or `create_elmer(...)`).
10. `utilities.create_run_script(sim_path)` (or `create_elmer_run_script(sim_path, settings)`).
11. To actually simulate: a working `run_palace` (Palace binary via Apptainer/Spack, on Linux/WSL)
    and `combine_snp` must exist on `PATH` in the execution environment — this repo does not, and
    cannot, provide those. Do not attempt to invoke `palace`/`ElmerSolver` directly; go through the
    generated `run_sim`/`run_elmer` wrapper, which in turn goes through those two `PATH`-resolved
    commands.
12. Simulation results land as `<model_basename>.s<N>p` (+ optionally `_dc`/`_deembedded` variants)
    next to `port-S.csv`, produced by `combine_snp` → `combine_extend_snp.py` (§9) — read them with
    `skrf.Network(...)`, same as every example in this repo does; there is no gds2palace-native
    result-reading API.
