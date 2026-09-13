# gds2palace FAQ

This FAQ is written for readers who already know a commercial EM tool such as
HFSS, ADS Momentum, Sonnet, or AWR. It focuses on where gds2palace works
differently from those tools, not on syntax you can already find in the
[workflow user's guide](userguide_md_format/gds2palace_workflow_userguide.md)
(the full settings/API reference) or by reading
[`util_simulation_setup.py`](../workflow/gds2palace/util_simulation_setup.py)
directly. If setupEM (the PySide6 GUI front-end) is more your speed than
writing Python, see [its own FAQ](https://github.com/VolkerMuehlhaus/setupEM/blob/main/doc/FAQ.md)
instead — much of the conceptual ground (ports, stackup Variables, mesh
philosophy) is shared, and this document cross-links back to it rather than
repeating it.

The short version of the biggest mindset shift: **gds2palace has no GUI of
its own.** It is a Python package that turns a GDSII file plus an XML
"stackup" file into a [gmsh](https://gmsh.info/)-meshed 3D FEM model and an
[AWS Palace](https://awspalace.org/) (or Elmer FEM) input file, driven
entirely by a script you write or generate. There is no project database, no
port editor, no built-in optimizer — and no assumption that a human is
sitting at a keyboard clicking through it, which is precisely what makes it
straightforward to drive from automation or an AI coding agent (see that
section below).

## Contents

[Getting started](#getting-started)  
[Input files](#input-files)  
[Ports](#ports)  
[Frequencies](#frequencies)  
[Simulation settings](#simulation-settings)  
[Mesh](#mesh)  
[Running the solver](#running-the-solver)  
[Output and results](#output-and-results)  
[Elmer FEM alternative](#elmer-fem-alternative)  
[Starting from scratch for a new technology](#starting-from-scratch-for-a-new-technology)  
[Automation and AI-agent-driven workflows](#automation-and-ai-agent-driven-workflows)  
[Other topics](#other-topics)

## Getting started

### Do I need setupEM, or any GUI at all, to use gds2palace?

No. setupEM is one optional GUI front-end that generates the same kind of
model script you could write by hand; EMStudio plays the same role for the
openEMS flow. Every example under [`more_examples/`](../more_examples/) and
[`workflow/`](../workflow/) is a plain `.py` file you run with `python
model.py` — there is no requirement that it was ever opened in a GUI.

### What's the minimum I need to build a model?

A GDSII layout, an XML stackup file describing the process's metal/via/
dielectric stack, and a script that: builds a `settings` dict (mesh size,
frequency sweep, margins, ...), defines `simulation_ports` (which GDS marker
layers are ports and which metal layers they connect), calls
`stackup_reader.read_substrate()` and `gds_reader.read_gds()`, then
`simulation_setup.create_palace(excite_ports, settings)`.
[`workflow/palace_line_viaport.py`](../workflow/palace_line_viaport.py) is
about as short as this gets in practice; the ["Simulation model file in
detail"](userguide_md_format/gds2palace_workflow_userguide.md#simulation-model-file-in-detail)
chapter of the user's guide walks through every part of it.

### What actually gets generated when I run a model script?

`palace_model/<script_basename>_data/` next to the script: `config.json`
(the Palace input file), the `.msh` mesh file, `port_information.json`
(exact port geometry in microns), and a `run_sim` script. After the solver
runs, that directory also gets an `output/<script_basename>/` subtree with
`palace.json` (DOF, solve time, peak RAM), `port-S.csv`, and — if adaptive
mesh refinement was used — one `iterationN/` subfolder per refinement pass.

## Input files

### Why two separate files (GDS + XML) instead of one project database?

Geometry lives in plain GDSII and the process stackup lives in a separate
XML file; the two are combined only when the model script runs. This keeps
the same GDSII layout reusable across `gds_viewer`, `gds_prepare_for_EM`,
and the independent openEMS flow, which needs its own, differently-modeled
stackup file for the same technology (see below).

### Which stackup XML format should I use — the legacy one or the newer one?

Whichever an example you're copying already uses works fine; the reader
supports every format generation back to the original absolute-position
`schemaVersion="2.0"`. For a new stackup, prefer the current
Reference-relative + `<Variables>`/`"="`-expression format
(`schemaVersion="3.1"`) — it's order-independent and lets you parameterize
values instead of hand-computing absolute Z positions. [`more_examples/XML_stackup_format_examples`](../more_examples/XML_stackup_format_examples)
is a tutorial walking through each generation with real before/after
snippets; [`doc/XML_stackup_format/evolution_of_stackup_file_format.md`](XML_stackup_format/evolution_of_stackup_file_format.md)
and [`XML_stackup_format.md`](XML_stackup_format/XML_stackup_format.md) are
the full references.

### How do I override a stackup Variable from my script, without editing the XML?

`stackup_reader.read_substrate(XML_filename, variable_overrides={'Name': value})`.
[`more_examples/derived_layers_and_resistors/palace_resistors_rsil.py`](../more_examples/derived_layers_and_resistors/palace_resistors_rsil.py)
uses this for chip thickness; [`more_examples/EM_temperature_coefficient`](../more_examples/EM_temperature_coefficient)
uses the identical mechanism to sweep an operating temperature that every
temperature-dependent metal's `Conductivity` expression depends on — a good
template if you want a "vary one stackup parameter across runs" script of
your own.

### What if a simulation layer isn't drawn directly in the GDSII, like a foundry resistor formed from process layers?

Use a `<DerivedLayer>`: a boolean (`AND`/`OR`/`NOT`) or resize operation on
other GDSII or derived layer numbers, resolved automatically by
`gds_reader.read_gds()`. [`doc/XML_stackup_format/derived_layers.md`](XML_stackup_format/derived_layers.md)
is the full reference; [`more_examples/derived_layers_and_resistors`](../more_examples/derived_layers_and_resistors)
is a complete worked example (IHP `Rsil`/`Rppd`/`Rhigh` recognized from
poly/implant/contact layers).

### Can I reuse the openEMS stackup file here, or the other way round?

No. The Palace/Elmer FEM stackup and the openEMS FDTD stackup encode
different modeling assumptions — for example how the MIM capacitor
dielectric is handled, and whether conductors get a surface-impedance
boundary condition or a solid meshed volume. Using the wrong one for a given
solver can cause meshing errors or silently wrong results.

### Two conductor layers stacked directly on top of each other cause a meshing error. Why?

Two `Type="conductor"` layers must always be separated by a `Type="via"`
layer. Conductors are meshed as hollow surface shells, not solid volumes
(see ["Understanding volumes and surfaces created from GDSII"](userguide_md_format/gds2palace_workflow_userguide.md#understanding-volumes-and-surfaces-created-from-gdsii)),
so two of them touching directly leaves the mesher nothing solid to connect
through.

## Ports

### There's no port editor. What exactly goes in the GDS, and how does the script pick it up?

A port is an ordinary GDSII polygon on a marker layer number not used by the
process stackup (usually 201 and up). In the script, `simulation_ports.add_port(simulation_setup.simulation_port(portnumber=..., source_layernum=..., ...))`
maps that layer number to a port. In-plane ports are drawn as rectangles
(`target_layername=...`, `direction='x'/'y'` etc.); via ports are drawn as a
zero-width line — a box with zero size in x or y — (`from_layername=...`,
`to_layername=...`, `direction='z'`).
[`workflow/palace_line_viaport.py`](../workflow/palace_line_viaport.py) is
the simplest real example of the latter.

### Can a port reference an artificial ground plane instead of a real metal layer?

Yes — declare a zero-thickness `Type="sheet"` stackup layer with
`Material="PEC"` (a reserved name, no `<Materials>` entry needed) positioned
wherever you need it, and use it as a via port's `to_layername`. [`more_examples/core_transistor_3port_bce`](../more_examples/core_transistor_3port_bce)
does exactly this to get 3 independent via ports onto a transistor's
Base/Collector/Emitter terminals, which have no shared physical ground plane
nearby. Because it's a zero-thickness sheet, Palace represents `PEC` there
as an exact ideal-conductor boundary condition, not an approximation — the
approximation only applies when `PEC` is used on a real 3D conductor/via
*volume* (see that example's README for the distinction).

### Why does a port have a "voltage" setting, and why would I set it to zero?

Palace doesn't use port voltage as a physical quantity; this workflow
repurposes it as an excite/don't-excite flag. `simulation_ports.all_active_excitations()`
returns the port numbers with nonzero voltage, and `create_palace(excite_ports, settings)`
takes that whole list in one call — Palace solves each active excitation as
part of the same run. A port left at voltage 0 is still present and
terminated, but its row/column in the output S-parameter file is padded
with zeros rather than holding real simulated data.

### Can I define a balanced/differential port directly?

Not as a built-in feature — every excited port is its own row/column in the
n-port Touchstone output, and a single-ended-to-mixed-mode reduction is your
own postprocessing (typically with scikit-rf). Getting the reference-
impedance convention right when doing this by hand is a real, easy-to-get-
subtly-wrong step — [`more_examples/mesh_convergence/AGENTS.md` §2.6](../more_examples/mesh_convergence/AGENTS.md#26-analyze-the-results)
has a detailed writeup of the "engineering" vs. Bockelman-Eisenstadt
mixed-mode conventions and a real bug this caused, with a from-scratch
derivation method for a mixed single-ended/differential port set.

### Are results de-embedded to the port reference plane, like a calibration standard would do?

Not through a calibration structure such as TRL or SOLT — there are none in
this flow. Instead, `combine_extend_snp.py` (see [Output and
results](#output-and-results)) estimates the parasitic series inductance the
lumped port geometry introduces from a flat-ribbon calculation and cascades
a negative version of it onto the result, written as a separate
`_deembedded` Touchstone file. Treat it as a geometric correction, not a
calibrated de-embedding.

### Can I use wave ports for a more accurately calibrated reference plane?

No — Palace itself supports wave ports, but this workflow only implements
lumped ports; see [the user's guide](userguide_md_format/gds2palace_workflow_userguide.md#using-wave-ports-instead-of-lumped-ports-not-supported).

## Frequencies

### What is the adaptive frequency sweep, and how does it compare to HFSS's interpolating sweep?

The same idea: Palace solves a limited number of actual frequency points and
interpolates a dense output sweep from them (a reduced-order model), enabled
by default with `settings['adaptive_mesh_iterations']`-independent
`amr_tol`/`amr_max_dof` controlling the underlying adaptive mesh refinement
rather than the frequency interpolation itself. More output frequency points
still generally costs more time, since each interpolation point needs
solved data nearby.

### Can I simulate specific fixed frequencies, or get a field dump at one frequency?

`settings['fpoint']` adds discrete frequencies on top of the `fstart`/
`fstop`/`fstep` sweep; `settings['fdump']` additionally writes a field dump
at each listed frequency, for viewing in ParaView (there's no built-in field
plotter). See ["Adaptive mesh refinement at selected frequencies
only"](userguide_md_format/gds2palace_workflow_userguide.md#adaptive-mesh-refinement-at-selected-frequencies-only)
for how these interact.

### Why can't I simulate at 0 Hz, and how is DC handled?

FEM frequency-domain solvers can't solve at exactly 0 Hz. Ask for `fstart=0`
and gds2palace nudges the actual start frequency up slightly instead — you'll
see something like `WARNING: Start frequency changed from DC to 0.01 GHz!`
in the console — and `combine_snp` extrapolates a DC value into a separate
`_dc` Touchstone file from the low simulated points. Always check that file
before trusting it; it's an extrapolation, not a simulated data point.

## Simulation settings

### Where's the full reference for what goes in the `settings` dict?

There's no single exhaustive table — read [`util_simulation_setup.py`](../workflow/gds2palace/util_simulation_setup.py)
directly for a key you're unsure about (search for `get_optional_setting`
calls, which show the default). The most commonly used keys: `fstart`/
`fstop`/`fstep`/`fpoint`/`fdump`, `refined_cellsize`/`refined_cellsize_override`,
`meshsize_max`, `cells_per_wavelength`, `adaptive_mesh_iterations`/`amr_tol`/
`amr_max_dof`, `order`, `margin`/`air_around`, `boundary`, `preprocess_gds`,
`merge_polygon_size`, `preview_only`/`no_preview`/`no_gui`. The [user's
guide's `settings` chapter](userguide_md_format/gds2palace_workflow_userguide.md#settings)
covers the everyday ones with examples.

### What does mesh/FEM order mean, and which should I use?

The polynomial degree of the FEM basis functions — order 1 (faster, less
accurate), order 2 (Palace's default, recommended), order 3 (slowest, most
accurate, Palace-only — Elmer has no cubic solver). Order 1 is fine for a
quick sanity check of port setup or layout, not for a number you'd report;
see the [mesh convergence studies](../more_examples/mesh_convergence/README.md)
for real order-1-vs-2 error data on five actual structures.

### What does `z_thickness_factor` do?

It scales the effective thickness used for a conductor's side-wall surface
impedance separately from its true top/bottom surfaces, to correct for
over-estimating low-frequency conductor cross-section. See ["Conductor loss
modelling"](userguide_md_format/gds2palace_workflow_userguide.md#conductor-loss-modelling)
for the derivation and test cases — and note the related limitation
described in the next question.

### Why is my simulated DC/low-frequency resistance wrong for a narrow trace?

Conductors here are meshed as hollow surface shells with a surface-impedance
boundary condition — a skin-effect/high-frequency approximation. For a trace
whose width is only on the order of its own metal thickness, the side-wall
contribution that approximation can't resolve becomes a large fraction of
the cross-section, giving an inaccurate DC/low-frequency resistance. It's
not an issue at high frequency (genuinely in the skin-effect regime) or for
a normally-proportioned trace. [`more_examples/EM_temperature_coefficient`'s
README](../more_examples/EM_temperature_coefficient/README.md) walks through
hitting this with a 2 µm-wide test line and switching to the standard,
much-wider `line_simple_viaport` structure instead. See also ["Limits of
conductor loss calculation"](userguide_md_format/gds2palace_workflow_userguide.md#limits-of-conductor-loss-calculation).

### What boundary condition types are available?

Each of the six outer box faces independently: `ABC` (absorbing, plays the
role of a radiation boundary), `PEC`, or `PMC`. PML isn't implemented in AWS
Palace yet.

## Mesh

### Why is the mesh so much coarser here than in openEMS?

This FEM workflow models conductors as hollow shells with a surface
impedance boundary condition, so there's no need to mesh into skin depth the
way a solid-conductor FDTD/FEM tool (like openEMS) does. 2-5 µm is a good
`refined_cellsize` starting point for most IHP SG13G2 models.

### Can I refine one layer more finely than the global mesh setting?

`settings['refined_cellsize_override'] = [['LayerName', value_um], ...]`
pins specific metal layers to their own fixed cell size regardless of what
the rest of the sweep varies — used in the mesh convergence balun_mim study
to keep a wide reference layer coarse while refining everything else.

### How fine does my mesh actually need to be, and is adaptive mesh refinement worth it?

Don't guess — [`more_examples/mesh_convergence`](../more_examples/mesh_convergence)
is five worked convergence studies on real IHP SG13G2 structures (a coil, a
transformer, three different couplers/baluns) with concrete
mesh-size/order/AMR-iteration recommendations and the actual Max|ΔS| numbers
behind them; [`palace_summary.py`](../scripts/README.md) can render the
AMR convergence chart for a run of your own with one command.

## Running the solver

### Palace is Linux-only. What actually happens on Windows?

gds2palace generates model files (`config.json`, the mesh) on any platform,
including Windows — that part has no Palace dependency. The Palace *solver*
itself needs Linux: WSL, a native Linux machine, or a remote Linux host
reachable over SSH. See the [top-level README](../README.md)'s system
requirements and [`building-palace-apptainer.md`](building-palace-apptainer.md)/
[`building-palace-spack.md`](building-palace-spack.md) for installing it.

### How do I actually run a model once it's generated?

Every generated `_data` directory gets a `run_sim` script
(`utilities.create_run_script()`), which calls a `run_palace config.json`-
style wrapper followed by `combine_snp` for Touchstone conversion — see
[`scripts/README.md`](../scripts/README.md) for `run_palace` (local/
apptainer) and `run_palace_remote` (scp the model over, run it, scp results
back over SSH). Passwordless SSH (key-based auth) is required for the
remote variant to work non-interactively.

### My `run_sim` script can't find `run_palace`/`combine_snp` when run from a remote script, but it works fine when I SSH in interactively. Why?

A non-interactive `ssh host "command"` typically does **not** source
`~/.profile` or `~/.bashrc` — so a PATH extension that lives there (common
for a `scripts/` directory holding `run_palace`/`combine_snp`) is invisible
to that command, even though the exact same command works fine once you're
actually logged in. Fix it by sourcing the profile explicitly in the remote
command, e.g. `ssh host "source ~/.profile && ./run_sim"`.

### Can this scale out to a cluster or run multiple MPI ranks?

Yes — Palace supports MPI-parallel runs (`palace -np N config.json`, however
your `run_palace` wrapper invokes it), whether from an apptainer container or
a native/spack build. Scaling to a full cluster is possible the same way it
would be for any Palace install; this workflow only generates the input
files and a simple run wrapper, not cluster job submission.

### What's the difference between `preview_only`, `no_preview`, and `no_gui`?

All three suppress some part of gmsh's interactive FLTK window:
`preview_only=True` shows the unmeshed geometry and stops there (no
meshing/solve at all — useful for a quick geometry/port sanity check);
`no_preview=True` skips *just* the unmeshed-geometry preview but still
meshes and shows the meshed model; `no_gui=True` suppresses every gmsh
window and proceeds straight through meshing and config generation with no
display at all — the one you want for a fully headless/automated run. A
common typo (`settings['nogui']` instead of `settings['no_gui']`) is
silently ignored rather than erroring, which can leave a "hung" headless run
actually blocked in a GUI event loop with no visible window — see
[Automation and AI-agent-driven workflows](#automation-and-ai-agent-driven-workflows)
for how to spot this.

## Output and results

### Palace writes CSV. Where does the Touchstone file come from?

`combine_snp` (which runs `combine_extend_snp.py`) scans the output
directory and converts Palace's or Elmer's raw `port-S.csv` into standard
`.sNp` Touchstone files, including the de-embedded variant. `run_sim` already
calls this automatically as its last step. See [`scripts/README.md`](../scripts/README.md).

### What are the `_dc` and `_deembedded` files next to my main result?

`_dc` is the DC-extrapolated variant (see [Frequencies](#frequencies)
above); `_deembedded` has the estimated port series inductance removed (see
[Ports](#ports)). The plain result has neither suffix.

### How do I check whether a run actually finished, from a script?

`python scripts/palace_summary.py <path>` prints DOF, mesh size, solve time,
peak RAM and (for AMR) error indicators, and — usefully for automation —
**exits with a nonzero status if any run it looked at has no results yet**,
so it can be chained after `run_palace` to detect completion without parsing
`palace.json` yourself.

### How do I plot results without setupEM?

[`plot_snp.py`](https://github.com/VolkerMuehlhaus/plot_snp) (a standalone,
separate scikit-rf-based script/repo) for a quick look, or load the
Touchstone file with `skrf.Network`
directly and plot with matplotlib yourself — use the `Agg` backend
(`matplotlib.use("Agg")` before importing `pyplot`) and `fig.savefig(...)`
instead of `plt.show()` for a headless/scripted run.

### Is there a circuit-model extraction tool?

`snp2le` (a separate open-source tool, which setupEM's Model Fit button
wraps) extracts a lumped-element SPICE/Spectre netlist from an S-parameter
result. For narrowband, device-specific fits the `lumpedmodel` project has
simple calculation-based extractors, and a scikit-rf vector-fit script
handles arbitrary n-port black-box fitting.

## Elmer FEM alternative

### When would I use Elmer instead of Palace?

Elmer is a second, independently-implemented FEM solver this workflow can
target instead of Palace — useful for cross-checking a result, or if you
specifically need thermal simulation (Palace doesn't do that). It solves
every frequency point directly rather than interpolating, has no
zero-voltage-port excitation shortcut (its constraint-modes analysis solves
every defined port in one run regardless of voltage), doesn't yet support
sheet-resistor layers or the side-wall thickness correction Palace uses for
low-frequency conductor loss, and generally runs slower for a large sweep.
See ["Using gds2palace with Elmer FEM for EM
simulation"](userguide_md_format/gds2palace_workflow_userguide.md#using-gds2palace-with-elmer-fem-for-em-simulation)
in the user's guide.

### Can I do thermal (heat conduction) simulation with this workflow?

Yes, via Elmer — [`more_examples/thermal_simulation_using_Elmer`](../more_examples/thermal_simulation_using_Elmer)
is the complete worked example (GDSII + stackup thermal material properties
→ Elmer mesh → `ElmerSolver` → temperature field), including the setupThermal
GUI alternative and how to define heat sources/constant-temperature
boundaries.

## Starting from scratch for a new technology

### How do I build a stackup for a foundry PDK that isn't already provided?

Hand-write (or copy and adapt) an XML stackup file following [`doc/XML_stackup_format/XML_stackup_format.md`](XML_stackup_format/XML_stackup_format.md) —
every dielectric's thickness/permittivity, every metal/via layer's GDSII
layer number/thickness/conductivity/Z-position, and loss tangent data if
available. setupEM's Stackup Editor (`Tools > Edit Stackup XML...`, with a
live cross-section preview, and an ADS Momentum `*.subst`/`*.ltd` importer)
is a GUI convenience for this — gds2palace itself has no importer of its
own; you're editing the XML directly or via that GUI.

### How do I validate a brand-new stackup before trusting it on a real design?

Simulate something with a known answer first — a microstrip line sized for
50 Ω on a known layer pair, checked against hand calculation — before
trusting the stackup on a real design. The single microstrip line and balun
examples in the [user's guide's Examples chapter](userguide_md_format/gds2palace_workflow_userguide.md#examples)
are a reasonable template for this kind of sanity check.

## Automation and AI-agent-driven workflows

### Is gds2palace actually suitable for driving from a script or an AI agent, not interactively?

Yes, and this is close to its native mode rather than a workaround: every
model is already "just" a Python script, gmsh's interactive window can be
fully suppressed (`settings['no_gui'] = True`), and there's no license
server or GUI state to manage. [`more_examples/EM_temperature_coefficient/palace_tcoef.py`](../more_examples/EM_temperature_coefficient/palace_tcoef.py)
is a small real example that builds two model variants (different
temperatures) in one headless script run with no user interaction.

### Can an agent generate the GDSII geometry itself, not just the stackup and ports?

Yes, with plain [gdspy](https://gdspy.readthedocs.io/) — no GUI needed
there either. [`more_examples/inductor_synthesis_no_external_library`](../more_examples/inductor_synthesis_no_external_library)
is the deep end of this: a fully automated pipeline that generates candidate
inductor layouts by code across a geometry sweep, runs a fast gds2palace
pass on each, refines the best candidates toward a target L/frequency, and
finalizes a full-accuracy layout — with no human decision in the loop past
setting the target and sweep ranges.

### What does a "generate several variants, simulate, compare" pipeline look like end to end?

[`more_examples/mesh_convergence/AGENTS.md`](../more_examples/mesh_convergence/AGENTS.md)
is written specifically as a step-by-step playbook for an AI coding agent
reproducing this kind of study: how to measure a layout's real feature sizes
without a GUI (KLayout in RBA batch mode), which settings to vary and how,
concrete gotchas (see the next two questions), how to hand off to a remote
Palace host, and — importantly — a checklist of what's safe to decide
autonomously versus what's design intent you should confirm with the user
first (frequency range, true port reference impedances, whether a test
structure includes its real compensation components, and so on).

### What's the most common way a headless/automated run silently breaks?

Two, both encountered in practice: (1) `settings['nogui']` (missing
underscore) is silently accepted as an unrecognized key rather than
erroring, defaulting `no_gui` back to `False` — gmsh then sits blocked in
its `gmsh.fltk.run()` GUI event loop with no visible window in a
non-interactive session, which looks like a hang; check the OS-level CPU
usage of the process (near-zero after the first few seconds is the
tell — a real meshing pass keeps the CPU busy) rather than assuming it's
just slow. (2) Python fully buffers stdout when it isn't attached to a
terminal, so a long generation run's progress can appear to print nothing
at all until it finishes when redirected to a log file — use `python -u`,
or just watch the filesystem for the expected `.msh`/`config.json` to
appear.

### How does an agent (or script) actually get a model onto a Palace solver, given Windows can't run one?

The same `run_palace`/`run_palace_remote` scp/ssh hand-off a human would use
(see [Running the solver](#running-the-solver)) — there's nothing
agent-specific about it beyond the non-interactive-shell PATH gotcha
mentioned there (`ssh host "source ~/.profile && ./run_sim"`). Run
variants sequentially rather than in parallel unless you've confirmed the
remote host actually has spare cores/RAM for concurrent solves — AMR runs in
particular can consume most of a machine's RAM on their own.

### How should an agent choose settings like frequency range or mesh size instead of guessing?

Some things are directly measurable from the GDS or inferable from the
stackup (feature size → mesh cell size, via pitch → `merge_polygon_size` —
[`AGENTS.md` §2.1](../more_examples/mesh_convergence/AGENTS.md#21-understand-the-geometry-before-choosing-any-mesh-sizes)
has concrete KLayout-batch-mode snippets for measuring both without a GUI).
Others are design intent that has to be asked rather than derived — the
target frequency band, how the user actually runs Palace, and (for a
differential structure) the *true* external reference impedances rather
than whatever `port_Z0` the simulation ports happen to use for convenience.
[`AGENTS.md` §4](../more_examples/mesh_convergence/AGENTS.md#4-questions-to-ask-the-user-before-starting-a-new-study)
is a concrete checklist of which is which.

### Can an agent verify a result without a human looking at a plot?

To a real extent, yes: confirm the expected `.msh`/`config.json` files exist
rather than trusting a clean process exit; chain `palace_summary.py` (exits
nonzero if a run has no results yet) after `run_palace` to detect completion
programmatically; and where an independent closed-form answer exists,
compare against it directly instead of only checking "did it run" —
[`more_examples/EM_temperature_coefficient`](../more_examples/EM_temperature_coefficient)
computes an expected trace resistance from the stackup's own conductivity
equation and compares it against the simulated S21, and the mesh_convergence
balun_mim study verifies a MIM capacitor's EM-simulated value against its
GDS text-label nominal value the same way.

## Other topics

### What does this cost, compared to a commercial FEM or MoM license?

gds2palace, AWS Palace, and Elmer FEM are all open source and free to use —
no license server, node-locking, or per-seat cost. You still need to build
or install the actual solver binaries yourself (see [Running the
solver](#running-the-solver)).

### Does this only work for RFIC layouts, or can I simulate a PCB the same way?

The workflow doesn't care what the geometry represents — GDSII plus an XML
stackup is the only requirement. One of the shipped examples imports a PCB
lowpass filter layout on RO4003 substrate into KLayout, saves it as GDSII,
and simulates it with a stackup built for that PCB material (see
`palace_pcb_lowpass.py` in the [user's guide's example list](userguide_md_format/gds2palace_workflow_userguide.md#list-of-examples)).

### Is there a schematic-and-layout co-simulation view, like ADS linking a schematic to Momentum?

No — this is a layout-in, S-parameters-out EM flow only, with no schematic
capture or live circuit-simulator link. Touchstone results are meant to be
imported into whatever circuit simulator you already use.
