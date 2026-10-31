# Change list 

This is an (incomplete) list of changes and new features.

## 31 October-2026
gds2palace 0.9.4

**Fix**  
`read_gds()` reads each GDS layer number once. A stackup can use one GDS layer for several stackup layers (one drawn shape makes all of them, e.g. a MIM top plate and the dielectric below it); `read_gds()` read such a layer once per stackup layer, so its polygons were in the model several times. The current IHP stackups have no shared layers, so their models do not change. `read_gds()` also no longer adds `gds_boundary_layers` to the caller's layer list.

## 31 October-2026
gds2palace 0.9.3

**New features**  
Multielement ports: several shapes on one port layer now become one port with one element per shape, the elements in parallel (a Palace `LumpedPort` with `Elements`; the port impedance stays the given Z0). Use it for a terminal that is spread over several strips, e.g. the source fingers of a multi-finger transistor. Before, only the last shape read became the port, and the others stayed in the model as surfaces without a port. `port_information.json` has one entry per element, with its `element` number. `combine_extend_snp.py` takes one Z0 per port for the Touchstone option line and treats the port inductances of the elements as parallel for de-embedding. Elmer models stop with an error for a multielement port.

**Documentation**  
User's guide, FAQ and AGENTS.md: the IHP SG13G2 PDK resistors as sheets in the EM model. The sheets have the drawn size and the nominal sheet resistance, without the PDK's width offset and contact end resistance; in Palace, rhigh and rppd come out about 10 % below their PDK value, rsil within about 2 %. See "Accuracy of IHP SG13G2 PDK resistors as sheets" in the user's guide.

## 22 October-2026
gds2palace 0.9.2

**New features**  
The result tools `combine_extend_snp.py` (Palace results to Touchstone) and `palace_summary.py` (run summary: unknowns, run time, peak RAM, AMR error) are now installed with the pip package, as `gds2palace.scripts`: `python -m gds2palace.scripts.palace_summary <path>` and `python -m gds2palace.scripts.combine_extend_snp`. They need scikit-rf (`pip install scikit-rf`), which gds2palace does not install. `utilities.get_scripts_dir()` returns their folder. The files in `scripts/` are unchanged, so the Linux install script still downloads them from there.

**Documentation**  
User's guide and AGENTS.md: a via port drawn as a box with an area becomes a sheet along the box's left edge (xmin, if it is taller than wide) or bottom edge (ymin), as the code has always done; the documentation said "along its center line". Draw via ports as lines.

## 18-20 October-2026
gds2palace 0.9.1

**New features**  
A pre-built Apptainer image for Palace 0.18.1 is now available: `apptainer pull palace_0181.sif oras://ghcr.io/volkermuehlhaus/palace_0181:latest`. It is compiled for a common processor level (`x86_64_v3`, AVX2), so it runs on all Intel processors since 2013 and all AMD processors since 2017. The Linux and Windows install scripts now download this image by default; `--palace-version 016` still gives the 0.16 image. The generated `run_palace` script now calls `apptainer -q`, which hides Apptainer's info messages.

The latest IHP stackup files (`SG13G2_FEM_200um.xml`, `SG13G2_FEM_200um_passi3D.xml`, `SG13CMOS5L_200um.xml`) are now installed with the pip package, so a model no longer needs a copy of the repository. `utilities.get_stackup_path('SG13G2_FEM_200um.xml')` returns the full path of one; `utilities.get_stackup_path()` without an argument prints the stackup folder and the available files. Legacy stackups are not included.

**Fixes**  
For very long polygon edges, mesh refinement along the conductor edges is more robust now.

`scripts/combine_extend_snp.py`: with different port impedances, the Touchstone option line now has one Z0 per port, in port order (ports with the same Z0 as port 1 were left out before).  

**Documentation**  
[`building-palace-apptainer.md`](building-palace-apptainer.md) and [`building-palace-spack.md`](building-palace-spack.md) are rewritten for end users: simple steps for Palace 0.18.1, an explanation of each tool, and a table of problems and solutions. Both end with technical notes for AI agents. The Apptainer guide explains how to build an image that runs on other computers: without a fix for libCEED, which always compiles for the build computer's processor, a self-built image can stop with `Illegal instruction` on other computers.

New study [`amr_conformal`](../more_examples/mesh_convergence/mesh_convergence_D-band_balun/amr_conformal/README.md) on the D-band balun: conformal vs. nonconformal AMR, `UpdateFraction`, and AMR at a single frequency followed by one full sweep on the saved mesh.

## 15-17 October-2026
gds2palace 0.9.0

**New features**  
`settings['conductor_model']` chooses the conductor model in one setting: 
- `'surface'` (default, unchanged behavior), 
- `'solve_inside'` (conductors as volumes, the former `filled_metals = True`) or  
- `'solve_inside_skin'` (volumes with skin layers, new).  

This replaces `settings['filled_metals']`, see "API changes".  

`'solve_inside_skin'` splits each conductor into thin layers along all its faces plus a core, so that the mesh has thin cells next to the conductor surface (where the skin effect puts the current) while the cell size along the surface stays at `refined_cellsize`. See "Accuracy at high frequency" in the user's guide, chapter "Conductor loss modelling".

New study [`more_examples/conductor_models`](../more_examples/conductor_models/README.md): accuracy and cost of the three conductor models on six SG13G2 structures and straight lines, against the most accurate earlier results and, for L6n2, the measurement.

Each study in `more_examples/mesh_convergence` was extended, to cover the conductor model also. This compares the three models on five SG13G2 structures: at a 2 µm mesh, the peak Q of coils on TopMetal1/TopMetal2 (2-8 µm traces) is 18-30 % too high with `'surface'`, 4-8 % too low with `'solve_inside'` and 2-3 % too low with `'solve_inside_skin'`, relative to `'solve_inside_skin'` at 1 µm.


**Documentation**  
Chapter "Conductor loss modelling" of the user's guide: the `z_thickness_factor` section is removed (with the L2n0 and microstrip tests and the Palace code walk-through), and so is the section "Transmission line compared with openEMS and measurement", which compared it with the full side wall thickness; the setup of that line and its measurement is now described in chapter "Dielectric loss modelling", `conductor_model` is the recommended choice. New section "Choosing the conductor model" with the errors and run times of the three models, and a table of what the errors mean for typical designs (VCO phase noise, insertion loss of LNA input matches and baluns, MIM capacitor Q, line loss). The same tables are in the FAQ. The code examples no longer set `z_thickness_factor`.

New section "Accuracy at high frequency" in chapter "Conductor loss modelling" of the user's guide. It also describes a limitation of the surface impedance model that was not documented: thin conductors that carry current on one face only, e.g. a Metal1-Metal5 ground plane under a line, get up to twice their real loss (line resistance of `palace_line_viaport.py` 21-41 % too high).

Run times of the conductor models in the user's guide ("Choosing the conductor model") and the FAQ now come from the conductor model study, which ran all models on one machine, one run at a time: relative to `'surface'`, `'solve_inside'` takes 1.25-1.7x and `'solve_inside_skin'` 1.5-3.5x the run time on coils and baluns at a 2 µm mesh. The earlier values (0.7-2.7x and 1.5-4.7x) came from machines shared with other runs.


**API changes**  
`settings['filled_metals']` is replaced by `settings['conductor_model']`. Existing scripts keep working: `filled_metals = True` is the same as `conductor_model = 'solve_inside'`, `False` the same as `'surface'`, with the same results, and the model script prints a note. Giving both settings with different meanings stops with an error. setupEM writes `conductor_model` from its next version on.

`settings['z_thickness_factor']` (thickness factor for the side walls of surface impedance conductors) is removed. It also changed the side wall impedance well into the skin effect regime, and the full thickness was closer to openEMS and measured data. A script that sets it to a value other than 1 gets a warning, and the full thickness is used, so its results change. The examples `palace_balun_mesh5.py` (gds2palace) and `palace_rfcmim.py`, `palace_demo_line.py`, `palace_balun_mesh2.py` (setupEM) used 0.33. For accurate conductor loss, use `conductor_model`.

All faces of a surface impedance conductor (top, bottom and side walls) are now one physical group, e.g. `TopMetal2_1`, instead of a horizontal and a vertical group (`TopMetal2_1_xy`, `TopMetal2_1_z`): without `z_thickness_factor`, both groups got the same conductivity and thickness. The mesh and the results are unchanged; only the group names in the mesh file, the Palace config and the Elmer input change, which matters for scripts or Paraview states that refer to the old names. The same applies to the lateral faces of vias in Elmer thermal models (`TopVia2_1` instead of `TopVia2_1_z`).

**Bugfixes**  
Conductor faces of surface impedance models were sorted into horizontal (`_xy`) and vertical (`_z`) groups by a normal computed from their boundary vertices, which gave a wrong or zero normal when a face was split, e.g. by a port: in a single-turn inductor, 68 % of the side wall area ended up in the horizontal group. Now the normal of the planar CAD face is used. This only mattered for `z_thickness_factor` other than 1, which is removed in this version (see above): before, only part of the side walls got the reduced thickness.

Reading a GDSII file printed "WARNING: could not auto-repair 2 invalid polygon(s)" for via ports drawn as a zero-width line (e.g. layers 201/202 in `workflow/line_simple_viaport.gds`), although the port works and nothing was changed. The check for self-intersecting polygons now only looks at layers that are meshed as solids (stackup metals and vias, dielectric boundary layers, derived layers), not at port and marker layers. Polygons that need repair are repaired as before.

## 12 October-2026
**Bugfixes**  
Port de-embedding in `combine_extend_snp.py` (the `_deembedded.sNp` and `_dc_deembedded.sNp` files) put the negative inductance of all ports in series at port 1, and nothing at the other ports. For a 2-port with 2.2 pH per port, port 1 was reduced by 4.4 pH and port 2 was not de-embedded at all; for a 3-port, port 1 got the sum of all three values. Now each port gets its own value, in port number order. The raw `.sNp` and the `_dc.sNp` files were not affected. De-embedded files created with earlier versions should be created again by running `combine_extend_snp.py` again. Thanks to Gianluca Simone and David Lurz (FAU) for finding and reporting this bug.

A second fix to the same port de-embedding: when `port_information.json` had no geometry data for a port, the values of the following ports moved up by one port (for a 3-port without data for port 2, port 2 got the value of port 3 and port 3 was not de-embedded). Each port now gets the value for its own port number, and a port without geometry data is not de-embedded. The de-embedding circuit is now built with scikit-rf's `Circuit` (named, explicit connections), as recommended by the scikit-rf maintainers, instead of chaining `connect()`.

## 7 October-2026
**Bugfix**  
gmsh's 3D Delaunay meshing can fail with "Could not recover boundary mesh: error 2", for example for a large `LBE` cavity or a `BACKSIDEGND` sheet that covers only part of the substrate bottom. Mesh generation now retries with gmsh's HXT algorithm in that case and prints a note. Models that mesh with Delaunay are not changed. If HXT also fails, model creation stops with an error instead of writing an incomplete mesh.

## 4 October-2026
**Documentation**  
The PDF user's guide is now generated from the Markdown user's guide [`userguide_md_format/gds2palace_workflow_userguide.md`](userguide_md_format/gds2palace_workflow_userguide.md), which is the only source from now on: `python doc/pdf_build/build_userguide_pdf.py`, see [`pdf_build/README.md`](pdf_build/README.md). A GitHub workflow builds the PDF when the guide changes and attaches it to each release.

The Markdown user's guide now includes the content that was only in the PDF so far: the surface impedance calculation in chapter "Limits of conductor loss calculation", the all-in-one installation script for Linux, and `filled_metals` in "What's New". Screenshots of code, XML stackup and Palace configuration excerpts are replaced by text (code blocks), so they can be searched and copied. All other figures have captions, broken links are fixed, and the `no_gui` example shows the current setting name.

## 2 October-2026
**Bugfixes**  
Via array merging (`merge_polygon_size > 0`) could short different metal shapes: closely spaced via arrays that connect different metal shapes above or below merged into one via. Now a merged via region that touches more than one metal shape above or below is built again: its vias are grouped by the metal shapes they connect, each group is merged on its own and clipped to the overlap of its metal shapes. The metal layers above and below each via layer come from the XML stackup. Vias without metal above or below stay unmerged. Merged vias that do not connect different metal shapes are not changed, so models without this problem give the same results as before.

Elmer thermal models failed with the [latest IHP stackups](../XML_stackup/latest/IHP/README.md) when the layout had shapes on `SUBGND` (250), `BACKSIDEGND` (251) or `REF_FOR_TRANSISTOR` (300), or when a constant temperature boundary used `BACKSIDEGND` as its target layer: these layers use the `PEC` material, which was rejected for thermal models ([issue #67](https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/issues/67)). Now thermal models ignore `PEC` sheet layers, in the same way as the resistor sheets, and a `PEC` layer can be the target of a constant temperature boundary. The same stackup file now works for EM and thermal models. `PEC` vias and conductor volumes, and heat sources with a `PEC` target layer, use the thermal properties of copper (401 W/m·K at 300 K, CRC Handbook) in thermal models, because `PEC` itself has no thermal conductivity. With `fill_factor_correction`, a merged `PEC` via array scales this value by its fill factor, like any other via material.

A heat source whose target layer has zero thickness (a sheet layer, `PEC` or resistor) now stops with a clear error message. Before, it failed with a gmsh "Degenerate box" exception.

Elmer thermal models failed with `SG13G2_FEM_200um_passi3D.xml` when TopMetal2 encloses an area, e.g. a ring or a heat spreader with openings: thermal models build all metals as volumes, and TopMetal2 then cuts the thin `Passive` layer into separate pieces, which stopped the model with an `AssertionError` ([issue #68](https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/issues/68)). Now all pieces of a dielectric keep its name and material.

A heat source can now have several polygons on its GDS source layer. Before, a second polygon stopped the model with `KeyError`. Overlapping or touching polygons of a source are merged into one volume. All volumes of a source share its power: the given power is the total for that source, not the power per polygon.

## 30 September-2026
**New features**  
`settings['complex_coarse_solve']` is a new gds2palace option, **enabled by default now**: Palace's sparse direct coarse solver now factorizes the full complex system instead of only its real part. **In many cases, this new setting will result in faster simulation.**  

Models that already converged without this new option give identical results with it, in about the same or less time (up to 2.7x faster for an inductor at 5 GHz). The cost is peak RAM, which depends on the model: 1.0-1.6x at order 2 and 1.5-1.9x at order 1 in these test cases. The setting doesn't depend on `filled_metals`: both failures above used surface impedance metals. Set it to `False` only if a model doesn't fit into memory, and then check the Palace output for `did NOT converge`.

Before, the Palace's own default (real part only) was used, so that absorbing boundaries, port resistances and losses were missing from the preconditioner. Some models did not converge at some frequencies, and got wrong S-parameters there:
- a D-band grounded CPW line (110-170 GHz, order 1) needed 176-437 iterations and failed at 170 GHz. With the new default it converges in 1 iteration per frequency (14-31 at order 2), 3.5-6x faster, with identical S-parameters.
- an inductor failed at 2.4 GHz, while the same model converged at 0.1 and 10 GHz. Its inductance came out as 1.1 nH instead of 2.5 nH. With the new default it converges in 1 iteration and runs 3.6x faster.


`settings['solver_maxits']` (default 400) and `settings['solver_tol']` (default 1e-6) make the Palace linear solver's iteration limit and tolerance configurable; both were hardcoded before.

**Bugfixes**  
The dielectric loss tangent (`DielectricLossTangent` in the XML stackup) was no longer written to the Palace model since the mesh redesign in v0.4.1, so all dielectrics were simulated as lossless. This is fixed: dielectrics with a non-zero loss tangent get Palace's `LossTan` again. The IHP SG13G2 stackups use lossless dielectrics and are not affected; lossy PCB substrates (e.g. RO4003, RO4350B) are.

**Examples and documentation**  
The [L6n2 inductor study](../more_examples/measured_vs_simulated/more_accurate_models_L6n2_v2/README.md) was rerun with `complex_coarse_solve` on the same meshes: identical results, and all 8 frequency sweeps took 1h 59m instead of 3h 43m, with the 1 µm reference model at 35 minutes instead of 74. The [original study](../more_examples/measured_vs_simulated/more_accurate_models_L6n2/README.md) stays available for comparison.

## 25-26 September-2026
**XML stackup files moved to separate folder**  
The stackup files are moved from the workflow folder to a separate XML_stackup folder, with a clear separation between legacy stackups (for compatibility) and latest stackups (recommended for new models).

**Examples and documentation**  
New [study on getting most accurate models for a 6nH octagon inductor](../more_examples/measured_vs_simulated/more_accurate_models_L6n2/README.md), with comparison to measured data. Besides the `filled_metals` option, this study also covers two other new features for improving accuracy: 
- via array merging gets a compensation factor for **accurate effective cross section** and
- **conformal (non-planar) dielectric** above TopMetal2 is modelled by a modified stackup.

All mesh convergence studies in the more_examples folder were re-written completely, see the [mesh convergence overview](../more_examples/mesh_convergence/README.md).

**New features**  
`settings['fill_factor_correction']` is a new option for improved accuracy when using via array merging. It is used together with via array merging (`merge_polygon_size > 0`) and is **not** active by default. Merging fills the gaps between vias with via material, so the merged via block has increased cross section = lower resistance than the real via array. With this option, each merged via polygon's conductivity is **multiplied by its fill factor** (original via area / merged polygon area). Merged vias on the same layer are grouped into separate materials when their fill factors differ by more than 20%, and each group uses its mean fill factor. The fill factors are only computed when the option is enabled, so `read_gds()` is not slowed down otherwise. The correction applies to Palace and to Elmer: Elmer EM scales the electrical conductivity, Elmer thermal the heat conductivity (including temperature table values).

**API Changes**  
`gds_polygon.is_via` and the `is_via` parameter of `all_polygons_list.add_rectangle()`/`add_polygon()` were removed: they were never set when reading GDSII and never used. Scripts that pass `is_via=` to these functions need to drop that argument.

## 22-23 September-2026
`settings['filled_metals']` is a new option for Palace, used for volume meshing of conductors instead of placing a surface impedance onto the side walls. This gives more accurate conductor loss at **low** frequency, where the skin depth is no longer small compared to conductor cross section. 

Note that the new volume meshing option is **not** the recommended default for Palace: volume meshing requires more RAM and simulation time, and will become inaccurate at higher frequencies, unless you really mesh into skin effect. See the new [`more_accurate_models_L6n2`](../more_examples/measured_vs_simulated/more_accurate_models_L6n2) example for a comparison of conductor volume mesh against surface-impedance modeling at several mesh sizes, checked against measurement.

`settings['adaptive_mesh_conformal']` is a new experimental option (default `False`) to use conformal AMR mesh refinement instead of Palace's default nonconformal (hanging-node) refinement. With conformal refinement, the mesh grows faster per AMR pass. For the D-band balun mesh convergence testcase, conformal AMR after 2 refinements (2.05 M unknowns, 30 min) was as accurate as the default nonconformal AMR after 4 passes (1.68 M unknowns, 44 min). This was measured with the real-only coarse solve that gds2palace used until 30 September 2026: on the refined nonconformal meshes, GMRES needed about twice as many iterations per solve (about 105 instead of 55). With `complex_coarse_solve` (the default since then), both need 22-32 iterations, and both take 23 min. At the same number of unknowns, both give the same accuracy, see the study [`amr_conformal`](../more_examples/mesh_convergence/mesh_convergence_D-band_balun/amr_conformal/README.md).

**Bugfixes**  
`combine_extend_snp.py` now handles a Palace run that was interrupted before finishing (e.g. terminated by setupEM's new memory-limit kill switch, or OOM-killed by the OS): a blank/truncated trailing CSV line, or Palace's own `"NULL"` placeholder for an excitation it never got to solve, previously either crashed with an `IndexError` or got silently written into the Touchstone output where it only surfaced later as an unhandled parse error in `scikit-rf`. Affected S-parameters are now written as `0.0 dB / 0 deg` instead, with a stdout warning and a comment line in the output Touchstone file listing exactly which parameters are unreliable, so a partial run degrades visibly instead of crashing or silently producing bad data.

## 18-September-2026
Detect a multi-chiplet stackup (one shared interposer referenced by several chiplet dies) from the Reference graph via `detect_chiplet_groups()`, and scope metal/dielectric z-range checks to each chiplet so same-height elements from different chiplets no longer get cross-linked or wrongly registered into each other's dielectric.

Added `find_z_overlap_pairs()`/`find_z_overlaps()` (overlapping same-scope dielectrics) and `find_missing_chiplet_boundaries()`/`find_missing_chiplet_boundary_warnings()` (a chiplet branch point or chiplet root Dielectric missing an explicit `Boundary=`, required once a stackup branches into chiplets).

**Bugfixes**  
Fixed a crash previewing a brand-new empty stackup, and a missing `.sNp` extension on `_dc`/`_deembedded` output when the model name itself contains a literal `.` (e.g. a dimension like `do82.41`).

Fixed a metal sitting exactly at its own reference dielectric's top edge (`ReferenceEdge="Top" Zmin="0"`) falling into the wrong, often shared dielectric instead - also fixes `Interposer_Backside` being dropped from `metals_inside`.

## 12-14-September-2026
Added an example ([`more_examples/EM_temperature_coefficient`](../more_examples/EM_temperature_coefficient/README.md)) for temperature-dependent conductivity in the XML stackup, to simulate loss vs. temperature. The corresponding .py simulation model loops over temperature and must be run from command line (not setupEM).

Added two reserved stackup materials that need no `<Materials>` entry: `PEC` (ideal conductor, on conductor/via/sheet Layers) and `AIR` (built-in default dielectric, overridable).

**Bugfixes**  
Fixed inductor synthesis spiral polygon vertices not landing exactly on the grid in the [inductor synthesis example](../more_examples/inductor_synthesis_no_external_library/synthesize_ihp_inductor_v4.py).

`read_gds()` now silently repairs self-intersecting GDSII "keyhole" polygons instead of failing much later with an opaque `assert dielectric_tags_unchanged` deep inside meshing.

Detect and fix overlap of lumped ports with metals on the same layer. Port wins now, this fixes the previous Palace/MFEM error ("a non-periodic face cannot have multiple boundary elements").

## 09-September-2026
Added `more_examples/mesh_convergence/`: five worked mesh convergence studies (how fine to mesh, whether adaptive mesh refinement helps) on real IHP SG13G2 structures — see the [overview](../more_examples/mesh_convergence/README.md) for what we found. Examples: [spiral inductor](../more_examples/mesh_convergence/mesh_convergence_inductor/README.md), [transformer](../more_examples/mesh_convergence/mesh_convergence_transformer/README.md), [D-band balun](../more_examples/mesh_convergence/mesh_convergence_D-band_balun/README.md), [2:1 edge-coupled balun](../more_examples/mesh_convergence/mesh_convergence_balun2x1/README.md), [MIM-loaded balun](../more_examples/mesh_convergence/mesh_convergence_balun_mim/README.md).

## 01-08-September-2026
Fixed a false-positive `Invalid surface found` print for via layers (e.g. `TopVia2`), introduced by the 06-September via lateral-surface change: those surfaces were being fed into the same boundary-condition builder used for regular conductor/sheet layers, which doesn't have a case for vias (they're already handled as domain conductors, not surface boundaries) and fell through to an "should never happen" branch. Via lateral surface physical groups are now only created for Elmer thermal models (their only real use, for Paraview visualization); the boundary-condition builder also now explicitly skips via layers instead of misreporting them as invalid.

Unified the Palace installation documentation: `doc/building-palace-spack.md` and `doc/building-palace-apptainer.md` are now the sole maintained, up-to-date step-by-step guides (targeting Palace 0.17.0, including the gds2palace `run_palace`/`combine_snp` integration and, for Apptainer, a Windows/WSL note and the prebuilt-0.16-image quick-start). The old `doc/Installing_Palace_using_Spack.pdf` and `doc/Installing_Palace_using_Apptainer.pdf` were removed — README.md, README_pypi.md, ARCHITECTURE.md and the userguide now link the Markdown guides directly instead.

Elmer thermal simulations can now use a direct linear solver (UMFPACK) instead of the iterative BiCGStabl solver, via `settings['iterative']=False` — useful when the iterative solver fails to converge on a large conductivity contrast between materials. Loosened the default iterative solver's convergence tolerance and raised its iteration cap, since the previous defaults could fail to converge on some models.

Fixed two related bugs in mesh generation that caused `IndexError`/`Could not create line` crashes on complex geometry involving OpenCASCADE boolean fragments: `is_vertical_surface()` used a threshold check (`int(abs(n))==0`) that misclassified almost every reconstructed horizontal face as vertical, and `get_surface_orientation()` computed a face's normal from only its first 3 boundary vertices, which could be near-collinear after a boolean fragment/union rebuilt the face. Both are now more robust (proper threshold, and Newell's method over all boundary vertices).

Vias now also get surface physical groups for their lateral (vertical) side faces, not just a volume — useful for Elmer thermal mesh visualization in Paraview. Top/bottom mating faces stay attributed to the metal layers the via connects to, to avoid a false "conductor layers touch" error.

Fixed Elmer EM simulations silently re-solving the same frequency twice: `write_elmer_frequencies()` combined the swept range with `fpoint`/`fdump` values without checking for overlap, so a frequency that happened to appear in both the sweep and `fpoint`/`fdump` landed on two separate lines of `frequencies.dat` — and Elmer's "Scanning" simulation solves every line as an independent full simulation task, addressed by index, not by value. The combined list is now de-duplicated before being written.

Elmer EM (S-parameter) simulations can now actually write field-dump data when `fdump` frequencies are set — this was silently doing nothing before. Fixed a crash when `fdump` was used without also specifying a frequency sweep (`fstart`/`fstop`), for both Palace and Elmer output. Fixed the generated Elmer run script on Windows, which used Linux-only `mpirun`/bash syntax and never actually worked there.

Fixed a crash in `resolve_derived_layers()`: `gdspy.boolean()` raises `IndexError` when called with an empty operand (e.g. a resistor recognition layer with no polygons in the current cell), which previously aborted the whole GDSII read. The boolean fold now short-circuits using the OR/AND/NOT identity instead whenever either operand is empty. Same fix applied to openems_ihp_sg13g2's independent copy of this reader.

## 21-August-2026
Allowed settings['air_around'] to be 0 on one or more sides, placing the simulation boundary flush with the dielectric/metal stack there instead of requiring a nonzero air gap on all six sides. 

Added PMC boundary support to the Elmer EM output. Verified by mesh/physics.sif generation only, not yet by an actual ElmerSolver run.

## 20-August-2026
Corrected a license inconsistency: the repository's LICENSE file and PyPI metadata said Apache-2.0, while every source file's own header comment already said GPLv3. The code headers were correct — gds2palace depends directly on gmsh (GPL-licensed, no linking exception covering this use), so GPLv3 is now the license declared everywhere (LICENSE file, pyproject.toml, and file headers that were previously missing one). Versions already published to PyPI (0.3.5, 0.3.6) were advertised as Apache-2.0 and that can't be changed retroactively; this correction applies from the next release onward.

The `gds2palace` PyPI package can now be built directly with `python -m build` from this repository, instead of maintaining a separate manually-synced copy. See `pyproject.toml` and `scripts/build_pypi_readme.py` at the repo root.

## 14-18-August-2026
Four major upgrades:

1) The stackup files now support derived layers, see folder `doc/XML_stackup_format` for details. This enables SG13G2 resistor in the stackup, see example in folder `more_examples`.  

2) gds2palace can now create thermal simulation models for Elmer, a multi-physics FEM solver. At this moment, thermal models can be excited by user defined thermal sources, see documentation in doc folder.  

3) Stackup XML files now support Reference-relative positioning: a `<Layer>` or `<Dielectric>`
can specify its position as an offset from the top or bottom edge of another named Layer or
Dielectric, instead of always using an absolute Zmin/Zmax value. This removes the need to
hand-recompute every dependent layer's z-position whenever a `<Dielectric Thickness="...">`
changes. See `doc/XML_stackup_format` for details, and `test_data/` for example files.

4) Stackup XML files now support a `<Variables>` block: named values (numbers or strings,
plain literals or `=`-prefixed expressions) that any attribute value anywhere in the file can
reference instead of a fixed value, removing the need to hand-copy the same physical value
into multiple attributes or files. A `<Variable>`'s value can itself be an expression built
from other variables (e.g. `Value="=metal_thickness + via_thickness"`), resolved regardless of
declaration order. A Python caller of `read_substrate()`/`parse_substrate()` can also override
a variable's value via the new `variable_overrides` argument - e.g. for a parametric sweep
script - without editing the XML file. See `doc/XML_stackup_format` for details, and
`more_examples/derived_layers_and_resistors` for a worked example.

Using derived layers, Reference-relative positioning, or thermal tables requires
`schemaVersion="3.0"` in the stackup file; using `<Variables>`/`=`-expressions requires
`schemaVersion="3.1"`. The reader now prints a warning if a stackup file declares a
`schemaVersion` newer than the version this gds2palace installation supports, so an outdated
installation is easier to notice.

As a side effect of derived layers, the handling of cutouts has been redesigned, and  model option `preprocess_gds` is no longer required.  

For users who prefer GUI driven model setup, the companion tool `setupEM` has been upgraded to support these new features. It also includes a GUI-driven XML stackup editor now. For thermal modelling using gds2palace with Elmer, `setupThermal` is the equivalent of `setupEM`, included in the same Python package.

https://github.com/VolkerMuehlhaus/setupEM

Development of gds2palace is now assisted by Claude Code, and some *.md files have been added to this repository to provide context for AI-assisted workflows.

## 14-June-2026
Completely redesigned the core mesh algorithm, which previously had thrown Palace MFEM error message for certain stacked chip configurations. Now, metals are properly cut from dielectrics no matter if they cross dielectric boundaries. Handling of gmsh dimtags to material properties was completely redesigned. Some error check were added on invalid port configurations, and invalid stackup configurations where two conductor layers touch directly with no via metal between them.


## 15-Mar-2026
A pre-generated apptainer container image for Palace version 0.16 is now available here:
https://github.com/users/VolkerMuehlhaus/packages/container/package/palace_016


To download the palace version 0.16 container into your current directory:

```
$ apptainer pull ghcr.io/volkermuehlhaus/palace_016:latest
```

This will save the container file to palace_016_latest.sif to your current directory. When using this container with scripts for the gds2palace workflow, make sure that the *.sif filename in the script matches your actual filename and file location where you stored the *.sif



## 10-Jan-2026
Fixed bug in port metadata information for in-plane ports, direction was not properly evaluated in some cases (check for "X" orientation was case sensitive). This resulted in incorrect port de-embedding, with width and length swapped for in-plane ports specified as "x" or "-x" direction. 


## 9-Dec-2025
Fixed an issue that caused mesh error when stacked objects overlapped exactly. Now, stacking objects with same size (resulting in shared surface) works correct.

A Python-based user interface for gds2palace named setupEM is now available. 
You can install this using pip install:

```
    pip install setupEM
```
This is work in progress with frequent updates, which can be installed using
```
    pip install setupEM --upgrade
```

Project source and documentation: 
https://github.com/VolkerMuehlhaus/setupEM


## 1-Dec-2025
Instead of always having the gds2palace directory in your working directory, 
you can also install gds2palace module to your venv using pip install:

```
    pip install gds2palace
```

https://pypi.org/project/gds2palace/

## 23-Nov-2025
- Added optional setting: options["fdump"] = [frequency] to create Palace points list with field dump enabled. 
- New example file palace_butlermatrix_dump93.py shows usage of fdump option. 

- Updated User's guide with new options, added a chapter listing examples

## 22-Nov-2025
- Added optional setting: options["fpoint"] = [frequency] to specify single frequency or list [] of frequencies separated by comma

## 21-Nov-2025
- Calculation of maximum meshsize is now per dielectric layer, means larger mesh cells in air and oxide.
- Added check to enforce gdspy version 1.6 or later, because gdspy 1.4.2 causes issues.
- Add version information for gds2python module files.
- Palace solver setting changed to AdaptiveTol = 2e-2

## 19-Nov-2025
- Improved combine_extend_snp code (postprecessing of results Palace to SnP) to handle more than 9 ports
