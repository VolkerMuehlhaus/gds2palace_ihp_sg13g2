# AGENTS.md: helping users with gds2palace

This file is for AI coding agents (Claude Code, Codex, Copilot, Cursor, ...)
that help a user build and run EM or thermal simulation models with
gds2palace. It explains the workflow, links to the right documentation for
each topic, and lists the rules and pitfalls that matter when you write or
change a model script for a user.

Read it before you write a model script. When this file and the code
disagree, the code is right: read the source instead of guessing.

## 1. What gds2palace does

gds2palace turns a **GDSII layout** plus an **XML stackup file** (metal, via
and dielectric layers with their materials) into a 3D FEM model:

- **AWS Palace** (main target): full-wave EM, S-parameters. gds2palace writes
  the gmsh mesh (`.msh`) and the Palace `config.json`. The Palace solver
  itself only runs on Linux (native, WSL, or a remote Linux host).
- **Elmer FEM, EM mode**: S-parameters with a second, independent FEM solver,
  for cross-checks.
- **Elmer FEM, thermal mode**: steady-state temperature from heat sources and
  constant-temperature boundaries.

The user always provides three things: the GDSII file, the XML stackup file,
and a **model script** in Python. The model script is the "project file":
there is no project database and no GUI state. Running it reads the stackup
and the layout, builds and meshes the geometry, and writes the solver input
files. The solver run is a separate step.

```
GDSII + XML stackup + model script (.py)
        |  python model.py
        v
palace_model/<model>_data/  config.json, <model>.msh, port_information.json, run_sim
        |  run_sim  (run_palace + combine_snp, on Linux)
        v
output/<model>/  port-S.csv, palace.json, ...  ->  <model>.sNp (Touchstone)
```

The target technology is IHP SG13G2 (and SG13CMOS5L), but any GDSII + stackup
works, e.g. PCB layouts.

## 2. Where things are

This file is at the root of the repository
<https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2>. All links below
are relative to that root.

**If the user only installed the package** (`pip install gds2palace`), the
documentation, examples and stackup files are not on their disk. Read them on
GitHub (prefix the paths below with
`https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/`), or
suggest cloning the repository. The user needs at least one XML stackup file
from [`XML_stackup/`](XML_stackup/) for any model.

To see the installed version and code: `pip show gds2palace`; the package
source is in the `gds2palace` folder of the venv's `site-packages`. In a
clone, it is [`workflow/gds2palace/`](workflow/gds2palace/).

### Documentation map

| Topic | Document |
|---|---|
| Overview, installation, system requirements | [`README.md`](README.md) |
| User's guide (full workflow, settings, ports, examples, Elmer) | [`doc/userguide_md_format/gds2palace_workflow_userguide.md`](doc/userguide_md_format/gds2palace_workflow_userguide.md) (also as PDF in [`doc/`](doc/), generated from the Markdown, see [`doc/pdf_build/`](doc/pdf_build/README.md)) |
| FAQ, including an "Automation and AI-agent-driven workflows" chapter | [`doc/FAQ.md`](doc/FAQ.md) |
| Code structure, how the mesh and config are built | [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) |
| Change log | [`doc/CHANGES.md`](doc/CHANGES.md) |
| Which stackup file to use | [`XML_stackup/README.md`](XML_stackup/README.md), [`XML_stackup/latest/IHP/README.md`](XML_stackup/latest/IHP/README.md) |
| XML stackup format reference | [`doc/XML_stackup_format/XML_stackup_format.md`](doc/XML_stackup_format/XML_stackup_format.md) |
| Derived layers (layers computed by boolean operations) | [`doc/XML_stackup_format/derived_layers.md`](doc/XML_stackup_format/derived_layers.md) |
| Stackup format tutorial, step by step | [`more_examples/XML_stackup_format_examples/`](more_examples/XML_stackup_format_examples/) |
| Installing the Palace solver | [`doc/building-palace-apptainer.md`](doc/building-palace-apptainer.md), [`doc/building-palace-spack.md`](doc/building-palace-spack.md), [`scripts/install_linux/`](scripts/install_linux/README.md), [`scripts/install_windows/`](scripts/install_windows/README.md) |
| Running Palace, Touchstone conversion, run summary | [`scripts/README.md`](scripts/README.md) |
| Basic example scripts | [`workflow/`](workflow/) (see [`workflow/README.md`](workflow/README.md)) |
| Advanced examples, index | [`more_examples/README.md`](more_examples/README.md) |
| Mesh size, FEM order, adaptive mesh refinement: measured advice | [`more_examples/mesh_convergence/README.md`](more_examples/mesh_convergence/README.md) |
| Running a mesh convergence study as an agent | [`more_examples/mesh_convergence/AGENTS.md`](more_examples/mesh_convergence/AGENTS.md) |
| Elmer thermal simulation | [`more_examples/thermal_simulation_using_Elmer/Elmer_Thermal_Workflow.md`](more_examples/thermal_simulation_using_Elmer/Elmer_Thermal_Workflow.md) |

### Code map (read these instead of guessing)

| File | Contents |
|---|---|
| [`workflow/gds2palace/util_simulation_setup.py`](workflow/gds2palace/util_simulation_setup.py) | `create_palace()`, `create_elmer()`, `create_elmer_thermal()`, ports, thermal objects. Every optional `settings` key is read with `get_optional_setting(settings, key, default)`: search for that to see all keys and their defaults |
| [`workflow/gds2palace/util_stackup_reader.py`](workflow/gds2palace/util_stackup_reader.py) | `read_substrate()`, XML stackup parsing |
| [`workflow/gds2palace/util_gds_reader.py`](workflow/gds2palace/util_gds_reader.py) | `read_gds()`, GDSII reading, via array merging, derived layers |
| [`workflow/gds2palace/util_utilities.py`](workflow/gds2palace/util_utilities.py) | output paths, `create_run_script()` |

## 3. Input files

### GDSII layout

- `read_gds()` reads the cell named `cellname`, or the first top-level cell if
  that name doesn't exist. Hierarchy is flattened.
- Only the layer numbers in `layerlist` and the datatypes in `purposelist` are
  read. IHP drawing data is datatype 0: use `purposelist=[0]`.
- Units: the GDSII coordinates are used as they are, in units of
  `settings['unit']` (normally `1e-6`, i.e. microns).
- **Ports** are polygons on extra layers that are not in the stackup, by
  convention 201 and up, one layer per port (see section 5).
- Holes and cutouts are handled automatically. The `preprocess` argument of
  `read_gds()` is obsolete and only prints a note. (Older documentation says
  it is required for cutouts; that is no longer true.)
- A user can generate GDSII by code, e.g. with gdspy:
  [`more_examples/inductor_synthesis_no_external_library/`](more_examples/inductor_synthesis_no_external_library/)
  builds layouts entirely in Python.

### XML stackup

- **For new models, use the files in [`XML_stackup/latest/IHP/`](XML_stackup/latest/IHP/)**
  (`SG13G2_FEM_200um.xml`, `SG13G2_FEM_200um_passi3D.xml`,
  `SG13CMOS5L_200um.xml`). They need gds2palace 0.5.0 or newer. Most bundled
  examples still use [`XML_stackup/legacy/`](XML_stackup/legacy/); that is fine
  for those examples. The table "Legacy files and their replacement" in
  [`XML_stackup/latest/IHP/README.md`](XML_stackup/latest/IHP/README.md)
  lists the latest file to use instead of each legacy file.
- **gds2palace stackups and gds2openEMS stackups are not interchangeable**,
  even for the same technology. They model e.g. the MIM dielectric and the
  conductors differently. Never use a gds2openEMS stackup file with gds2palace
  or the other way round: it gives meshing errors or wrong results.
- Chip and air thickness are `<Variables>` in the latest files. Change them
  from the script without editing the XML:
  `stackup_reader.read_substrate(XML_filename, variable_overrides={'total_thickness': 100})`.
  Unknown variable names stop with an error.
- Layer types: `conductor` (metal), `via`, `sheet` (zero thickness, e.g.
  resistors and ground sheets), `dielectric` (a brick drawn in GDSII). **Two
  conductor layers must never touch directly**; there is always a via layer
  between them.
- Reserved material names: `PEC` (ideal conductor, no `<Materials>` entry
  needed) and `AIR`.
- Extra layers in the latest IHP stackups:
  - `SUBGND` (GDS 250): PEC sheet on top of the EPI layer.
  - `BACKSIDEGND` (GDS 251): PEC sheet at the bottom of the substrate.
  - `REF_FOR_TRANSISTOR` (GDS 300): PEC sheet used as a port reference for
    transistor ports, see [`more_examples/core_transistor_3port_bce/`](more_examples/core_transistor_3port_bce/).
  - Resistor sheets `RHIGH`, `RPPD`, `RSIL`, created by derived layers from
    the drawn PDK layers.

  These layers only appear in the model if the layout has shapes on them (or,
  for derived layers, on their source layers).
- Layers that are not drawn directly (resistors, conformal passivation) are
  `<DerivedLayers>`: boolean operations on other layers. `read_gds()` resolves
  them automatically from the stackup.
- For a new technology, the user writes or adapts a stackup XML. setupEM's
  stackup editor (`Tools > Edit Stackup XML...`) is a GUI for this. Validate a
  new stackup with a structure that has a known answer, e.g. a 50 Ω line.

## 4. Writing a model script

Start from the example closest to what the user wants (same port type, similar
structure), not from scratch. Good starting points:

| Use case | Example |
|---|---|
| Simplest model: thru line with two via ports | [`workflow/palace_line_viaport.py`](workflow/palace_line_viaport.py) |
| Inductor | [`workflow/palace_L2n0.py`](workflow/palace_L2n0.py), [`more_examples/measured_vs_simulated/`](more_examples/measured_vs_simulated/) |
| MIM capacitor | [`workflow/palace_rfcmim.py`](workflow/palace_rfcmim.py) |
| Many ports, field dump | [`workflow/palace_butlermatrix.py`](workflow/palace_butlermatrix.py), [`workflow/palace_butlermatrix_dump93.py`](workflow/palace_butlermatrix_dump93.py) |
| Transistor parasitics, ports to an artificial ground | [`more_examples/core_transistor_3port_bce/`](more_examples/core_transistor_3port_bce/) |
| Resistors from derived layers, stackup variables | [`more_examples/derived_layers_and_resistors/`](more_examples/derived_layers_and_resistors/) |
| Several model variants from one script | [`more_examples/EM_temperature_coefficient/`](more_examples/EM_temperature_coefficient/) |
| PCB instead of RFIC | [`workflow/palace_pcb_lowpass.py`](workflow/palace_pcb_lowpass.py) |
| Elmer thermal | [`more_examples/thermal_simulation_using_Elmer/`](more_examples/thermal_simulation_using_Elmer/) |

Older examples in `workflow/` add a local `gds2palace` folder to `sys.path`
before `from gds2palace import *`. With the pip package installed, that line
is not needed; it does no harm either.

### Template

This is a complete model script for the pip-installed package and a latest
IHP stackup. Every value marked `# ASK` is design intent: get it from the user,
don't invent it.

```python
import os, sys
from gds2palace import *     # stackup_reader, gds_reader, simulation_setup, utilities

# ---------- input files ----------
gds_filename = "my_layout.gds"           # ASK
XML_filename = "SG13G2_FEM_200um.xml"    # from XML_stackup/latest/IHP/, copied next to the script
cellname = ""                            # "" = first top-level cell
merge_polygon_size = 0                   # via array merging distance in um, 0 = off (see below)

script_path = utilities.get_script_path(__file__)
model_basename = utilities.get_basename(__file__)
sim_path = utilities.create_sim_path(script_path, model_basename)   # palace_model/<model>_data
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------- settings ----------
settings = {}
settings['unit'] = 1e-6              # GDSII coordinates are in microns
settings['margin'] = 50              # um, dielectric oversize around the layout
settings['fstart'] = 0               # Hz, 0 is replaced by a small value (no DC in FEM)    # ASK
settings['fstop'] = 50e9             # Hz    # ASK
settings['fstep'] = 1e9              # Hz, output step (adaptive sweep interpolates)
settings['refined_cellsize'] = 2     # um, mesh size at metal edges
settings['cells_per_wavelength'] = 10
settings['meshsize_max'] = 70        # um
settings['order'] = 2                # FEM order, 2 for reportable results
settings['no_gui'] = True            # no gmsh window: required for unattended runs

# ---------- ports ----------
simulation_ports = simulation_setup.all_simulation_ports()
# via port between two metals: zero-width line drawn on GDS layer 201
simulation_ports.add_port(simulation_setup.simulation_port(
    portnumber=1, voltage=1, port_Z0=50, source_layernum=201,
    from_layername='Metal1', to_layername='TopMetal2', direction='z'))
# in-plane port on one metal: rectangle drawn on GDS layer 202
simulation_ports.add_port(simulation_setup.simulation_port(
    portnumber=2, voltage=1, port_Z0=50, source_layernum=202,
    target_layername='TopMetal2', direction='x'))

# ---------- read stackup and layout ----------
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML_filename)
layernumbers = metals_list.getlayernumbers()
layernumbers.extend(simulation_ports.portlayers)
allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0],
                                  metals_list=metals_list, merge_polygon_size=merge_polygon_size,
                                  gds_boundary_layers=dielectrics_list.get_boundary_layers(),
                                  cellname=cellname)

# ---------- create the model ----------
settings['simulation_ports'] = simulation_ports
settings['materials_list'] = materials_list
settings['dielectrics_list'] = dielectrics_list
settings['metals_list'] = metals_list
settings['layernumbers'] = layernumbers
settings['allpolygons'] = allpolygons
settings['sim_path'] = sim_path
settings['model_basename'] = model_basename

excite_ports = simulation_ports.all_active_excitations()
config_name, data_dir = simulation_setup.create_palace(excite_ports, settings)
utilities.create_run_script(sim_path)    # writes run_sim into the _data folder
```

Use `simulation_setup.create_elmer(excite_ports, settings)` instead of
`create_palace()` for an Elmer EM model; for thermal, see section 7.

### Settings

Required: `unit`, `margin`, `fstart`, `fstop`, `refined_cellsize`, plus the
model data keys set at the end of the template. Optional keys and defaults
(from `util_simulation_setup.py`; check there for the current list):

| Key | Default | Meaning |
|---|---|---|
| `fstep` | 1/100 of the span | Output frequency step; the adaptive sweep doesn't solve every point |
| `fpoint` | `[]` | Extra discrete frequencies (Hz), also usable without fstart/fstop |
| `fdump` | `[]` | Like `fpoint`, plus a field dump for ParaView or setupEM's field viewer |
| `adaptive_sweep` | `True` | Palace adaptive frequency sweep |
| `cells_per_wavelength` | `10` | Coarse mesh away from metal edges, at `fstop`; 10 or more |
| `meshsize_max` | `70` | Upper limit of the mesh size, in `unit` |
| `refined_cellsize_override` | `[]` | Per-layer mesh size, e.g. `[['Metal3', 10], ['Metal2', 2]]` |
| `substrate_refinement` | `False` | Extra refinement into the substrate, rarely needed |
| `order` | `2` | FEM basis order: 1 = quick check only, 2 = normal, 3 = most accurate (Palace only) |
| `adaptive_mesh_iterations` | `0` | Palace adaptive mesh refinement (AMR) passes |
| `amr_tol` / `amr_max_dof` | `1e-2` / `2e6` | AMR stop criteria |
| `adaptive_mesh_conformal` | `False` | Conformal instead of hanging-node AMR (experimental) |
| `save_adaptive_mesh` | `False` | Keep the refined mesh for reuse |
| `complex_coarse_solve` | `True` | Full complex coarse solve; keep it on unless RAM runs out |
| `solver_maxits` / `solver_tol` | `400` / `1e-6` | Palace linear solver limits |
| `boundary` | 6 × `'ABC'` | xmin, xmax, ymin, ymax, zmin, zmax: `ABC`, `PEC` or `PMC` |
| `air_around` | `margin` | Air around the dielectrics, one value or 6 values; 0 is allowed |
| `filled_metals` | `False` | Solid metal volumes instead of surface impedance: better low-frequency R, more RAM and time |
| `fill_factor_correction` | `False` | Scale the conductivity of merged via arrays by their fill factor (needs `merge_polygon_size > 0`) |
| `z_thickness_factor` | `1` | Side-wall thickness factor for conductor loss, see "Conductor loss modelling" in the user's guide |
| `no_gui` / `no_preview` / `preview_only` | `False` | gmsh windows: none at all / skip the unmeshed preview / preview and stop |
| `save_gmsh_unrolled` | `False` | Also save the unmeshed gmsh geometry |
| `config_suffix` | `''` | Suffix for `config.json`/`port_information.json`, e.g. `'_fine'` |

**Unknown keys are silently ignored.** A typo such as `settings['nogui']`
leaves the default in place: with `no_gui` at `False`, gmsh opens a window and
an unattended run seems to hang. Double-check key names against the source.

### Ports

- Each port uses its own GDS layer (`source_layernum`), not used by the
  stackup. Add `simulation_ports.portlayers` to `layernumbers` before
  `read_gds()`, or the port shapes are not read.
- **Via port** (vertical): `from_layername` and `to_layername`, `direction='z'`
  or `'-z'`. Draw it as a **zero-width box** (a line) in GDSII: the port is a
  vertical 2D sheet. A box with an area is turned into a sheet along its center
  line.
- **In-plane port**: `target_layername`, `direction='x'`, `'-x'`, `'y'` or
  `'-y'`. Draw it as a rectangle on that metal's level.
- The sign of `direction` sets the polarity.
- A port can end on an artificial ground: a `Type="sheet"` layer with
  `Material="PEC"`, like `REF_FOR_TRANSISTOR` in the latest stackups.
- `voltage` is not a physical voltage here: **voltage 0 means "not excited"**.
  Palace then solves only the excited ports, and the S-parameter rows of the
  others are filled with zeros. For a full S-matrix, give every port a
  non-zero voltage.
- `port_Z0` is the port reference impedance.
- Only lumped ports are supported (no wave ports, no composite ports). Lumped
  ports add some series inductance; `combine_snp` writes an extra
  `_deembedded` file with an estimate of it removed.

### Via arrays

`merge_polygon_size > 0` merges vias on `Type="via"` layers that are closer
than this distance (µm) into one polygon. This gives far fewer mesh elements
for large via arrays. It never connects vias that land on different metal
shapes above or below (gds2palace 0.8.1 and newer). Typical values are 0.5 to 2 µm, at least the via
pitch of the arrays that should be merged. Merging fills the gaps with via
metal, which overstates the via conductance: set
`settings['fill_factor_correction'] = True` to correct it. If the GDSII file
already contains merged vias (e.g. from gds_prepare_for_EM or setupEM's
Simplify GDS), the original vias are gone and no correction is possible.

## 5. Running the model and the solver

1. **Generate the model**: `python model.py`. Without `no_gui`, gmsh shows the
   unmeshed geometry first; closing the window continues with meshing. Use
   `preview_only=True` for a quick geometry and port check without meshing.
   For unattended runs, set `no_gui=True` and use `python -u` (otherwise the
   output is buffered and a log file stays empty until the end).
2. **Check the output**: `palace_model/<model>_data/` must contain
   `config.json`, `<model>.msh`, `port_information.json` and `run_sim`. Don't
   rely on the exit code alone.
3. **Run Palace** with `run_sim` in that folder, on Linux. It calls
   `run_palace config.json` (a wrapper the user adapts to their Palace
   installation: native, apptainer, number of processes) and then
   `combine_snp`. `run_palace_remote` copies the model to a remote Linux host
   by scp, runs it there and copies the results back; it needs passwordless
   SSH. See [`scripts/README.md`](scripts/README.md). Ask the user how they run
   Palace; don't assume.
   - Over a non-interactive SSH command, the user's PATH may not include
     `run_palace`: use `ssh host "source ~/.profile && ./run_sim"`.
   - Run several models one after another unless the host has RAM and cores
     for parallel runs; AMR runs can use most of a machine's RAM.
4. **Check the run**: [`scripts/palace_summary.py`](scripts/README.md) prints
   degrees of freedom, solve time, peak RAM and AMR error indicators, and
   exits non-zero if a run has no results. Search the Palace log for
   `did NOT converge`: S-parameters at those frequencies are unreliable.

## 6. Results

- `combine_snp` (`combine_extend_snp.py`) converts Palace's `port-S.csv` to
  Touchstone `<model>.sNp`. Extra files:
  - `_dc`: a DC point extrapolated from the low-frequency data (FEM can't
    solve at 0 Hz); check it before use.
  - `_deembedded`: the estimated lumped-port inductance removed.
- Plot with [plot_snp](https://github.com/VolkerMuehlhaus/plot_snp)
  (`python plot_snp.py result.s2p S11 S21`), or with scikit-rf and matplotlib.
  For scripted runs use the `Agg` backend and `savefig()`, not `plt.show()`.
- Field dumps (`settings['fdump']`) are written for ParaView. setupEM has a
  built-in 3D field viewer, also usable from the command line: `fieldViewer`
  (run it with `--help`; `--screenshot out.png` renders without a window).
- Verify with physics where possible, not only "it ran": e.g. the resistance
  of a line from the stackup conductivity, or a capacitor's nominal value.
  [`more_examples/EM_temperature_coefficient/`](more_examples/EM_temperature_coefficient/)
  does this.

## 7. Elmer FEM

- **EM**: `create_elmer(excite_ports, settings)` instead of `create_palace()`.
  Elmer solves every frequency point (no interpolation), always solves all
  ports, and doesn't support sheet resistor layers. See "Using gds2palace with
  Elmer FEM for EM simulation" in the user's guide.
- **Thermal**: `settings['elmer_thermal'] = True` and
  `simulation_setup.create_elmer_thermal(settings)`. Heat sources and
  constant-temperature boundaries are polygons on extra GDS layers:

  ```python
  thermal_objects = simulation_setup.all_thermal_objects()
  thermal_objects.add_heatsource(simulation_setup.heatsource(
      power=0.1, source_layernum=201, target_layername='Metal1'))       # W, ASK
  thermal_objects.add_consttemp(simulation_setup.constanttemp(
      temp=298, source_layernum=202, target_layername='BACKSIDEGND'))   # K, ASK
  layernumbers.extend(thermal_objects.layers)        # before read_gds()
  settings['thermal_objects'] = thermal_objects
  ```

  - The power of a heat source is the total for all its polygons.
  - A heat source needs a target layer with a thickness (not a sheet).
  - A constant-temperature boundary uses only the z position of its target
    layer, so a PEC sheet such as `BACKSIDEGND` works.
  - All materials need `ThermalConductivity` in the stackup; the latest IHP
    stackups have it. In thermal models (gds2palace 0.8.1 and newer), PEC
    sheets are ignored, and PEC volumes use copper's thermal conductivity.

  Full guide: [`Elmer_Thermal_Workflow.md`](more_examples/thermal_simulation_using_Elmer/Elmer_Thermal_Workflow.md).

## 8. Choosing settings

Base these on the layout and on measured data, not on guesses:

- **Mesh size**: `refined_cellsize` 2 to 5 µm is a good start for IHP SG13G2.
  Tightly coupled structures (small gaps, high frequency) need finer meshes.
  [`more_examples/mesh_convergence/README.md`](more_examples/mesh_convergence/README.md)
  has measured recommendations for six structures.
- **FEM order**: 2. Order 1 only for checking ports and geometry.
- **AMR**: often not needed with a fine enough initial mesh; see the mesh
  convergence studies.
- **Margin and boundaries**: absorbing (`ABC`) boundaries need some distance
  from the structure; the examples use 30 to 100 µm.
- **Measure the layout** (smallest gap and width, via pitch) before choosing
  the mesh size or merge distance. [`more_examples/mesh_convergence/AGENTS.md` §2.1](more_examples/mesh_convergence/AGENTS.md#21-understand-the-geometry-before-choosing-any-mesh-sizes)
  shows how to do this without a GUI, using KLayout in batch mode.

## 9. Ask the user, don't decide

These are design decisions that the files can't tell you:

- Frequency range and points of interest, and whether field dumps are needed.
- Which GDS layers hold the ports, port type (via or in-plane), which metals
  they connect, polarity and reference impedance. For differential structures:
  the real reference impedances, not the convenience `port_Z0` values.
- Which stackup file (technology, chip thickness, planar or conformal
  passivation) and whether variables need overrides.
- How and where they run Palace (local Linux, WSL, remote host, cores, RAM).
- Accuracy versus run time (mesh size, order, AMR).
- For thermal models: heat source powers and the heat sink temperature and
  location.

## 10. Common mistakes

| Symptom | Cause |
|---|---|
| Unattended run "hangs" with no CPU load | `no_gui` not set (often a typo like `nogui`): gmsh waits in an invisible window |
| No output in a log file for a long time | Python buffers stdout: use `python -u` |
| Meshing error between two metals | Two conductor layers touch directly: a via layer must be between them |
| Meshing errors or wrong results with a stackup that "should work" | A gds2openEMS stackup used with gds2palace |
| Port missing or at the wrong place | Port layer not in `layernumbers`, wrong `source_layernum`, or the via port drawn with an area |
| Zero rows in the S-parameter file | Ports with `voltage=0` are not excited |
| Wrong resistance of narrow lines at low frequency | Surface impedance model: see "Limits of conductor loss calculation" in the user's guide; consider `filled_metals` |
| Unreliable S-parameters at some frequencies | `did NOT converge` in the Palace log; keep `complex_coarse_solve` on, raise `solver_maxits`, check the model |

## 11. Related tools

| Tool | Use |
|---|---|
| [setupEM / setupThermal](https://github.com/VolkerMuehlhaus/setupEM) (`pip install setupEM`) | GUI that builds gds2palace models without writing Python, runs Palace, plots results, has a stackup editor, a layout simplifier and a 3D field viewer. Its generated model scripts are normal gds2palace scripts |
| [gds_prepare_for_EM](https://github.com/VolkerMuehlhaus/gds_prepare_for_EM) (`pip install gds_prepare_for_EM`) | Simplifies tape-out GDSII before EM simulation: removes dummy fill and small cutouts, merges via arrays safely, replaces round pads |
| [gds2openEMS](https://github.com/VolkerMuehlhaus/gds2openEMS) (`pip install gds2openEMS`) | The same kind of workflow for the openEMS FDTD solver. Same model script structure, but **its own stackup files** |
| [plot_snp](https://github.com/VolkerMuehlhaus/plot_snp) | Plots Touchstone files: dB, phase, Smith chart |
| [KLayout](https://www.klayout.de/) | Viewing and editing GDSII, measuring the layout, drawing port shapes |
