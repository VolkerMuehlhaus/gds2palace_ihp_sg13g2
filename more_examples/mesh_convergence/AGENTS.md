# Reproducing a mesh convergence study (for AI agents)

This document is for an AI coding agent asked to run a mesh convergence
study with gds2palace — i.e. "how fine does the mesh need to be for this
layout, and is adaptive mesh refinement (AMR) worth it?" — and who has not
necessarily worked with this repo before. It assumes no prior gds2palace
knowledge and walks through the method used to produce the five studies
in this folder ([`mesh_convergence_inductor/`](mesh_convergence_inductor/),
[`mesh_convergence_transformer/`](mesh_convergence_transformer/),
[`mesh_convergence_D-band_balun/`](mesh_convergence_D-band_balun/),
[`mesh_convergence_balun2x1/`](mesh_convergence_balun2x1/),
[`mesh_convergence_balun_mim/`](mesh_convergence_balun_mim/)), so you
can reproduce the same kind of study on a new layout. Read [`README.md`](README.md)
in this folder first for the end-user-facing summary of *what* we found;
this document is about *how* to produce more studies like it.

## 0. Background: what gds2palace is and how the pieces fit together

- **What this repo does:** gds2palace turns a GDSII layout plus an XML
  "stackup" file (metal/dielectric layer definitions + material properties)
  into a 3D FEM model, meshes it with [gmsh](https://gmsh.info/), and writes
  a `config.json` that the [AWS Palace](https://awspalace.org/) solver
  consumes. Start with the [top-level README](../../README.md) for the full
  picture.
- **A model script** is a short Python script (see any `palace_*.py` file
  in the study folders for real examples) that: sets a `settings`
  dict (mesh cell size, frequency sweep, margins, FEM order, ...), defines
  `simulation_ports` (which GDS marker layers are ports, and which metal
  layers they connect), reads the stackup XML and the GDS, then calls
  `simulation_setup.create_palace(excite_ports, settings)`. That call is
  implemented in [`util_simulation_setup.py`](../../workflow/gds2palace/util_simulation_setup.py) —
  read it directly if you need to know exactly what a `settings` key does
  or what its default is; don't guess. [`util_stackup_reader.py`](../../workflow/gds2palace/util_stackup_reader.py)
  and [`util_gds_reader.py`](../../workflow/gds2palace/util_gds_reader.py) are
  the other two files worth knowing about (stackup XML parsing and GDS
  polygon extraction, respectively).
- **What gets generated:** running a model script creates
  `palace_model/<script_basename>_data/` next to the script, containing
  `config.json`, the `.msh` mesh file, `port_information.json` (exact port
  geometry in microns — useful for rendering labeled layouts, see §2.1),
  and a `run_sim` script. After the solver runs, that directory also gets
  an `output/<script_basename>/` subtree with `palace.json` (DOF, solve
  time, peak RAM — the fields §2.7 pulls numbers from), `port-S.csv`, and
  (if AMR was used) one `iterationN/` subfolder per refinement pass.
- **Touchstone conversion:** `port-S.csv` isn't directly usable by
  S-parameter tools. [`combine_extend_snp.py`](../../scripts/combine_extend_snp.py)
  (invoked via the `combine_snp` shell wrapper, which `run_sim` calls
  automatically) searches recursively for `port-S.csv` files and writes
  `.snp` Touchstone files, including a de-embedded variant with port
  parasitic inductance removed. See the [scripts README](../../scripts/README.md).
- **Summarizing a run:** [`palace_summary.py`](../../scripts/palace_summary.py) reads
  `palace.json` (and, for AMR runs, every `iterationN/palace.json` plus
  `error-indicators.csv`) and prints DOF / mesh elements / solve time /
  peak RAM / error indicators in one table — for AMR runs pass `--plot` to
  also render the iteration-vs-error convergence chart used in every study
  report here (`amr*_convergence.png`). Use this tool; don't hand-parse
  `palace.json` yourself unless you need a field it doesn't already expose.
- **The five existing studies are worked templates.** Before writing
  anything from scratch, look at the model scripts, `results/*.py`
  analysis scripts, and `mesh_convergence_report.md` in whichever study is
  structurally closest to your new layout:
  - a single coil → `mesh_convergence_inductor/`
  - a multi-port coupled structure with a center tap → `mesh_convergence_transformer/`
  - a tightly-coupled mm-wave structure → `mesh_convergence_D-band_balun/`
  - a differential structure with an **asymmetric turns ratio** (unequal
    primary/secondary reference impedances, e.g. 200 Ω : 50 Ω) →
    `mesh_convergence_balun2x1/`
  - a structure mixing a **single-ended port with a differential pair**
    (each at its own true impedance), a layer needing a fixed mesh size
    independent of the global sweep, or GDS-labeled component values
    (e.g. MIM caps) worth an independent EM check → `mesh_convergence_balun_mim/`

  Copying and adapting one of these is almost always faster and less
  error-prone than starting blank.

## 1. What a mesh convergence study is actually answering

Given one fixed layout, you re-run the same simulation at several mesh
settings and compare the results. The questions being answered are
practical, not academic:

- How coarse can the mesh be before the answer (S-parameters, and any
  structure-specific derived quantity like inductance or Q factor) starts
  to meaningfully change?
- Is AMR worth turning on for this structure, and if so, how many
  iterations before it stops helping?
- Is FEM order 1 an acceptable shortcut for a quick look, or does it
  introduce an error that order-1 mesh refinement can't fix?

There's no universal answer — the existing studies reached different
conclusions about AMR's value specifically *because* the answer depends
on the geometry. Don't import a conclusion from one study into a new one;
rerun the comparison.

## 2. Step-by-step method

### 2.1 Understand the geometry before choosing any mesh sizes

Don't guess a mesh cell size range. Measure the layout's actual smallest
features (trace width, gap between adjacent traces, overall footprint)
directly from the GDS, then pick a cell-size sweep that brackets those
numbers (e.g. if the narrowest trace/gap is ~5 µm, try something like
1/2/3/5 µm; if it's ~2 µm, go finer).

The most reliable way to measure this without a GUI is driving the local
KLayout install in batch mode with a small Ruby (RBA) script:

```
"<path to>\klayout_app.exe" -z -nc -rx -r measure.rb
```
(`-z` = headless, `-nc` = no config file, `-rx` = ignore implicit macros.)

Minimum trace width of a polygon, by shrinking it until it disappears:

```ruby
layout = ...; cell = ...; dbu = layout.dbu
region = RBA::Region.new(cell.begin_shapes_rec(layout.layer(gds_layer, 0)))
region.each do |poly|
  r1 = RBA::Region.new(poly)
  (1..80).each do |i|
    shrink_um = i * 0.25
    if r1.sized(-(shrink_um/dbu).round).is_empty?
      puts "min width ~#{2*(shrink_um-0.25)} um"
      break
    end
  end
end
```

Minimum gap between (possibly separate) polygons on one layer, by scanning
`Region#space_check` for the threshold where violations first appear:

```ruby
region = region.merged
(1..200).each do |i|
  d_um = i * 0.1
  ep = region.space_check((d_um/dbu).round)
  if !ep.is_empty?
    puts "min gap ~#{d_um} um"
    break
  end
end
```

Port locations: either read them off the model script's
`source_layernum` values and query that GDS layer's bounding box, or (if
the model has already been generated once) read the exact port geometry
straight out of `palace_model/<basename>_data/port_information.json`.

For a labeled layout picture (the "Layout" section every study report
opens with), reuse the exact rendering path already used in this repo —
either the `gds_viewer`-based Python renderer
([`render_labeled_layout.py`](mesh_convergence_transformer/results/render_labeled_layout.py)
in the transformer or balun study) or, if only KLayout is convenient, render
with KLayout batch mode and overlay port markers/labels with PIL afterward
(see [the inductor study's version](mesh_convergence_inductor/results/render_labeled_layout.py),
which reads centroids from `port_information.json`). Either way, describe
actual measured dimensions in the report text — not just "rendered with
gds_viewer's colors."

### 2.2 Decide what to sweep — and ask the user about anything design-specific

Reasonable defaults, confirmed against the existing studies:

- **Uniform mesh sweep:** several cell sizes bracketing the smallest
  measured feature, `adaptive_mesh_iterations=0`, FEM order 2 (Palace's
  default — keep it explicit in the settings for clarity).
- **AMR:** one variant, modest starting cell size, and cap
  `adaptive_mesh_iterations` at 2-3. Every study here found that Palace's
  AMR often doesn't reach its own error-indicator tolerance even after
  using its entire iteration budget, and that cost grows much faster than
  accuracy improves past the first couple of iterations — so don't let an
  agent (or a user) request a large iteration budget without flagging
  that it may buy very little for a lot of runtime/memory.
- **FEM order comparison (optional):** re-run a subset of the uniform
  sweep at `order=1` if the user wants a timing/accuracy trade-off
  comparison. Order 1 is dramatically faster but converges to a
  measurably different answer than order 2 regardless of mesh refinement
  — that's expected (a basis-function truncation error, not a
  discretization error) and worth stating plainly if you find it. Don't
  assume this offset behaves the same way across structures, either: the
  inductor study found a roughly mesh-independent constant offset, while
  the balun2x1 study found the order-1 error shrinks (without fully
  closing) as the mesh refines — check both, don't reuse a prior verdict.
- **Per-layer mesh overrides, if one layer needs a different cell size
  than the global sweep.** `settings['refined_cellsize_override'] =
  [['LayerName', value_um], ...]` (see `util_simulation_setup.py`) pins
  specific metal layers to a fixed `refined_cellsize` independent of
  whatever the global sweep varies — used in the balun_mim study to keep
  a wide ground/reference layer at a coarse fixed size while the sweep
  refines everything else, so the sweep isn't paying to over-refine a
  layer that doesn't need it.
- **Via-array merging**, if the layout has dense via arrays (e.g. under a
  MIM capacitor): `settings['merge_polygon_size']` controls how close
  polygons need to be before gds2palace merges them into one. Too small
  and each individual via becomes its own tiny mesh feature (expensive,
  no accuracy benefit); too large and it can accidentally merge two
  physically separate via arrays into one. Measure the actual via pitch
  and the minimum gap between separate arrays first (same KLayout
  `Region#sized`/merge-and-compare technique as §2.1's trace/gap
  measurement, just applied at a few candidate merge distances to see
  where the polygon count jumps) and pick a value with margin on both
  sides — see the balun_mim study for a worked example.

**Don't guess the frequency sweep, or assume Palace's default remote
execution setup.** These are the two things to actually ask the user
about before generating anything:

- Frequency range/step — this is design intent (what band the structure
  is used in), not something inferable from the GDS. This includes any
  single **design/eval frequency** used to pick specific-frequency columns
  in the delta-S tables (§2.6): ask for the actual number rather than
  auto-deriving one from the simulated response (e.g. the center of the
  peak-coupling band) — the transformer study originally did the latter
  and landed on a frequency nowhere near the structure's real 30 GHz
  target, which also masked the fact that a bare (uncompensated) coil
  pair doesn't match well at its actual operating frequency either.
- How they run Palace. It's Linux-only; a Windows workstation generates
  models but doesn't solve them (see the [top-level README](../../README.md)'s
  platform notes). Common patterns: a remote Linux host reachable over
  SSH, WSL, or a local Linux machine. [`run_palace`](../../scripts/run_palace)
  and [`run_palace_remote`](../../scripts/run_palace_remote) are reference
  implementations of the two ends of an ssh/scp hand-off pipeline — read
  the [scripts README](../../scripts/README.md) for how they fit together,
  and ask the user for their actual host/command rather than assuming SSH
  access or a specific solver installation method (apptainer vs. a native
  build both appear "in the wild"). If they do have SSH configured, a
  non-interactive `ssh host "command"` typically does **not** source
  `~/.profile` or `~/.bashrc` — verify whatever wrapper script the model's
  `run_sim` expects (e.g. `run_palace`, `combine_snp`) is actually on PATH
  in that non-interactive shell before assuming it'll work; `ssh host
  "source ~/.profile && command"` is one fix if it isn't.

### 2.3 Generate the model script variants

Copy an existing working model script for the target GDS+stackup (or
write a new one following the pattern in `util_simulation_setup.py` /
the existing studies' scripts) and vary **exactly one setting per axis**
across variants — same margin, frequency sweep, port definitions, etc.
everywhere, so any difference in the results is attributable to the
thing you're actually studying.

**A gotcha worth checking for every time:** the setting that suppresses
gmsh's interactive preview window is `settings['no_gui']` (underscore).
At least one pre-existing template script in this repo had it misspelled
as `settings['nogui']`, which `get_optional_setting()` silently accepts
as an unrecognized key and defaults `no_gui` to `False` — so headless
generation would appear to hang forever, because gmsh is actually sitting
in a blocking `gmsh.fltk.run()` GUI event loop with no visible window in
a non-interactive session. If a generation run seems stuck with no
output, check the OS-level CPU usage of the Python process (near-zero CPU
after the first few seconds strongly suggests this) rather than assuming
it's just slow — a real gmsh meshing pass keeps the CPU busy.

Run a variant headlessly with (exact invocation depends on how the
specific script wires up the check):

```
python <model_script>.py nogui
```

### 2.4 Generate + verify locally before touching a solver

Activate the Python venv that has gds2palace + gmsh installed (see this
repo's top-level docs for which one). Generate every variant, and confirm
each one actually produced a `.msh` file and a `config.json` — don't
assume a clean process exit means success without checking. Python fully
buffers stdout when it isn't a terminal, so redirected output from a
long-running generation may show nothing until it finishes; use `python
-u` for live progress, or just check for the `.msh` file directly.

Generate the cheapest variant first in the foreground and watch it
complete end-to-end before batching the rest — it's much cheaper to catch
a config mistake (or the `no_gui` gotcha above) on one quick run than
after kicking off eight of them.

### 2.5 Run the solver

Once you know how the user runs Palace (§2.2), the generic pattern is:

1. Copy the generated `_data` directory to wherever Palace actually runs
   (`scp -r`, or just `cp -r` if it's WSL/local).
2. Execute that directory's `run_sim` script there. It typically calls a
   `run_palace config.json`-style wrapper (solver invocation) followed by
   a Touchstone-conversion step.
3. Copy the resulting `output/` directory back.

Run variants **sequentially**, not in parallel, unless you've confirmed
the remote host has enough spare cores/RAM for concurrent solves — AMR
runs in particular can consume most of a machine's RAM on their own (see
any study's AMR results table for real numbers). Capture progress to a
log file and check in on it periodically rather than polling constantly;
solve times for a small sweep can range from seconds to hours depending
on mesh size, AMR iteration count, and structure complexity, so don't
assume a "few minutes" budget without evidence from at least one
completed run.

### 2.6 Analyze the results

For each variant, copy the de-embedded `.snp` file into a `results/snp/`
folder with a short, clear name (e.g. `<name>_mesh2.s2p`, not the raw
generated filename). Then:

- **S-parameter convergence** (always do this): overlay magnitude/phase
  plots across mesh variants, plus a delta-S table — `Max|ΔS|` as the
  largest linear complex-magnitude difference over the common frequency
  band between two variants (the standard HFSS-style convergence metric),
  reported both between successive mesh steps and against the finest mesh
  as a fixed reference. [`analyze_convergence.py`](mesh_convergence_inductor/results/analyze_convergence.py)
  (or the same file in the other studies) is a direct template; adapt the
  port count / mixed-mode reduction to match the new structure (a plain
  2-port needs none, e.g. the inductor study; a differential-pair
  structure needs a mixed-mode reduction, e.g. the transformer/balun2x1/
  balun_mim studies).
- **Decide raw vs. de-embedded S-parameters, and document the choice.**
  `combine_extend_snp.py` writes both a raw Touchstone and a
  de-embedded one (port parasitic inductance cascaded out). Either is a
  legitimate choice, but pick one per study and say so in the report
  (§2.7) — don't mix them across sections of the same report, and don't
  assume de-embedded is always "more correct" for a mesh-convergence
  comparison; the balun_mim study uses raw throughout because it's the
  more direct, reproducible quantity to track mesh-to-mesh.
- **Mixed-mode reduction: get the reference-impedance convention right,
  not just the port pairing.** There are two different, non-interchangeable
  definitions of a differential pair's self-impedance term depending on
  how "differential current" is defined:
  - The plain "engineering" convention (`Zdiff = Vdiff/I`, with `I` the
    actual current in one leg, driven as `I_a=-I_b`) — this is what a
    "100 Ω differential pair" means in RF/PCB design, and the convention
    used (and cross-validated against an independent ADS simulation) in
    the transformer/balun2x1/balun_mim studies: `Zbb = Z_ii-Z_ij-Z_ji+Z_jj`
    with **no** extra factor.
  - The Bockelman-Eisenstadt power-normalized convention
    (`Idm=(I_a-I_b)/sqrt(2)`), whose own `Zbb` term comes out to **exactly
    half** of the engineering value.

  These are easy to mix up silently: reusing a `1/sqrt(2)`-normalized
  cross term or a `/2`-normalized self term from a B&E-style derivation,
  then plugging it into the general unequal-impedance Z→S formula
  alongside an engineering-convention reference impedance (e.g. `Z02=100`)
  produces a plausible-looking but wrong result — it silently imposes a
  termination of `2×Z02`, not `Z02`. This exact bug was found and fixed
  in the balun_mim study (see that study's `analyze_baseline.py`
  docstring for the full derivation, and the report's §3 for the
  before/after numbers) — when a port set mixes single-ended and
  differential-pair ports (not two full differential pairs like the
  transformer/balun2x1 studies), derive the reduced 2-port from scratch
  by imposing the actual current constraint (`I_a=-I_b` on the pair, `I`
  free on the single-ended port) on the full Z-matrix rather than
  adapting a formula from a different port topology by pattern-matching.
  Sanity-check any new derivation the same way this repo already does:
  confirm `Zab≈Zba` (reciprocity), and where possible reduce to a known
  formula in a limiting case (e.g. setting all reference impedances equal
  should reproduce the plain equal-impedance Bockelman-Eisenstadt result).
- **Structure-specific derived quantities**, if applicable. For an
  inductor: differential impedance `Zdiff = Z11-Z12-Z21+Z22` from the
  2-port Z-matrix, then `L = Im(Zdiff)/ω`, `Q = Im(Zdiff)/Re(Zdiff)`,
  `R = Re(Zdiff)` (this is the same method an external `plot_inductor.py`
  utility uses, reimplemented directly in `mesh_convergence_inductor/results/plot_inductor_convergence.py`
  rather than depending on an external script). For a differential
  structure, amplitude/phase imbalance between the two differential
  outputs is a useful extra check: renormalize per-port with
  `skrf.Network.renormalize(z_new)` to each port's true impedance, then
  compare `|S_i1|` vs. `|S_j1|` directly; for the phase difference,
  `np.unwrap` the phase of the ratio along frequency and shift by a whole
  number of 360° turns to sit near the physically expected value (e.g.
  180° for two antiphase differential outputs) — don't plot a raw phase
  difference, it produces a spurious jump every time either phase crosses
  the ±180° branch cut even when the physical quantity is smooth (see
  balun_mim's `analyze_convergence.py`).
- **Don't report a "real load" / floating-impedance result for a
  structure that lacks its compensating components.** A transformer or
  balun's imaginary part is normally compensated by matching components
  (e.g. MIM capacitors) in the real circuit; a bare-coil (or bare-coupled-
  line) test structure without them will not present a realistic
  impedance to any real load at any frequency, including the design
  frequency. Deriving a floating-load `Zin` from the bare structure's
  Z-matrix and reporting it (or comparing it against mixed-mode `Sdd11`)
  invites the reader to draw a real-circuit-performance conclusion the
  simulation can't support. The transformer and balun2x1 studies
  originally included this analysis and later had it removed for exactly
  this reason (see those reports' "why there is no real load analysis"
  section) — if the model doesn't include the compensation network, stick
  to reporting the bare structure's mixed-mode S-parameters at its own
  port reference impedances, not a real-load-implied number.
- **Verifying a labeled component value against its EM simulation**, if
  the GDS has a component (e.g. a MIM cap) with its nominal value in a
  text layer: build a small standalone 1-port test structure isolating
  just that component (a lumped via port bridging its two terminals
  directly), extract the value from the 1-port Y-parameter (e.g.
  `C = Im(Y11)/(2*pi*f)` for a capacitor), and compare against the
  nominal value at a couple of frequencies (agreement across frequency
  confirms it's a real physical quantity, not solver noise). Expect the
  EM-simulated value to differ somewhat from a compact-model nominal
  value — routing parasitics between the port and the component's actual
  footprint are a real, physical contribution the compact model doesn't
  include, not necessarily an error; check whether refining the mesh
  closes some of the gap before concluding it's parasitic rather than
  numerical (see balun_mim's `verify_mim_capacitance.py` and its
  report's MIM capacitor verification section for a worked example,
  including extracting the nominal value from GDS text labels via a
  KLayout `RecursiveShapeIterator` — watch for the gotcha that
  `shape.text_trans.disp` returns a `Vector`, and `Trans * Vector` only
  applies rotation/mirroring, not translation; wrap it in
  `RBA::Point.new(...)` before the transform to get the correct absolute
  position).
- **AMR convergence chart:** just run `python ../../scripts/palace_summary.py
  <path to the AMR _data dir> --plot` — it reads `palace.json` from every
  iteration and the top-level run, and writes `convergence.png` for you.
  Copy it into `results/plots/`.
- Load and manipulate S-parameters with `skrf.Network` (scikit-rf); plot
  with matplotlib using the `Agg` backend (`matplotlib.use("Agg")` before
  importing `pyplot`) so it works in a headless session, and save PNGs
  rather than calling `plt.show()`.

### 2.7 Write the report

Match the structure used by the existing reports (each one's opening
`mesh_convergence_report.md` is a directly readable template):

1. A bullet-list header: model/stackup filenames, solver + key settings,
   frequency sweep, port definitions, execution notes. If the structure
   has a stated design/application target (e.g. a specific frequency, or
   whether compensation components like MIM caps are included in this
   particular test structure), say so here — don't bury it in a later
   section where it looks like an afterthought.
2. **Layout** — measured dimensions (trace width, gaps, footprint, port
   layout) from §2.1, not just a description of how the picture was
   rendered.
3. **Method** — which variants were generated and why.
4. **Uniform mesh sweep results** — a table with DOF, mesh elements,
   solve time, peak RAM, and error indicator norm/max per mesh size (all
   read straight from `palace.json` — see `palace_summary.py`'s field
   names if unsure which JSON keys these are).
5. **AMR results** — the same fields per iteration, plus the
   `amr*_convergence.png` chart, plus Max|ΔS| between successive
   iterations.
6. **S-parameter overlays + delta-S tables** (§2.6).
7. Any structure-specific results section (§2.6).
8. **Discussion/recommendation** — state a concrete, numbers-grounded
   recommendation (which mesh size, whether AMR helped, whether order 1
   is usable) for *this* structure. Don't reuse another study's verdict.
9. **"Where everything lives"** — a file tree of what's in the study
   folder and what each file/script regenerates.

Two placement details that keep the study easy to navigate: put
`mesh_convergence_report.md` at the **study's root** (not inside
`results/`, where it's easy to miss) with image links written as
`results/plots/...` to match; and keep generated meshes/raw solver output
(`palace_model/`) out of version control via this folder's `.gitignore`
— only the model scripts, GDS/XML inputs, `results/` (reports, CSVs,
plots, archived `.snp` files) need to be committed.

## 3. External tools this workflow depends on

- **[KLayout](https://klayout.de/)**, driven in RBA batch mode — precise
  geometry measurement (§2.1) and, if `gds_viewer` doesn't already cover
  it, ground-truth layout rendering.
- **gds2palace** (this repo) — GDS + XML stackup → gmsh mesh → Palace
  `config.json`.
- **[gmsh](https://gmsh.info/)** — the meshing engine gds2palace drives;
  you generally don't call it directly, but its FLTK preview window is
  the thing `no_gui` needs to actually suppress (§2.3).
- **[AWS Palace](https://awspalace.org/)** — the FEM solver. Linux-only;
  ask the user how they run it (§2.2).
- **[scikit-rf](https://scikit-rf.org/)** (`skrf`) — Touchstone I/O and
  all S-parameter/impedance math in the analysis scripts.
  `Network.renormalize(z_new)` re-references individual ports to their
  true impedance (used for per-port amplitude/phase imbalance checks,
  §2.6) — prefer it over hand-rolled renormalization math for that case,
  it's a vetted general-N-port implementation.
- **[matplotlib](https://matplotlib.org/)** (`Agg` backend) — every plot.
- **`combine_extend_snp.py` / `combine_snp`** (`../../scripts/`) — converts
  Palace's `port-S.csv` into Touchstone `.snp`, with port de-embedding.
- **`palace_summary.py`** (`../../scripts/`) — reads `palace.json`
  (+ AMR iteration subfolders) into a human-readable summary table, and
  can render the AMR convergence chart directly.

## 4. Questions to ask the user before starting a new study

Don't silently assume any of these — confirm them first:

- What frequency range/step matters for this design? Is there a specific
  design/eval frequency to highlight in the tables, and if so, what is it
  (don't auto-derive one from the simulated response — see §2.2)?
- What cell sizes should the uniform sweep use? (Propose a range based on
  measured feature size per §2.1, but confirm it — especially if it would
  mean many expensive runs.)
- Should AMR be included, and with what starting mesh / iteration cap?
- Is an FEM order 1 vs. order 2 comparison wanted?
- If the port set includes a differential pair (or more than one): what
  are the *true* external system impedances per port/pair (don't assume
  the simulation's `port_Z0` — often 50 Ω on every port for solver
  convenience — is the real intended impedance; e.g. an asymmetric turns
  ratio implies unequal primary/secondary impedances, and a mixed single-
  ended + differential port set has a true impedance per port *and* per
  differential pair)?
- Does this test structure include the components needed for it to behave
  like the final circuit (e.g. compensation/matching capacitors)? If not,
  don't derive or report a real-load/floating-impedance figure from it
  (§2.6) — only the bare structure's own mixed-mode S-parameters.
- Does the GDS have any component with a nominal value worth an
  independent EM check (e.g. a MIM cap with its value in a text layer)?
  If so, a small standalone 1-port verification structure (§2.6) is cheap
  extra confidence and worth proposing even if not explicitly requested.
- How does the user actually run Palace (remote host, WSL, local Linux),
  and is it OK to actually kick off runs now (could take anywhere from
  minutes to hours), or should scripts just be prepared for the user to
  run themselves?
