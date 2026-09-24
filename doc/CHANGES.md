# Change list 

This is an (incomplete) list of changes and new features.


## 22-23 September-2026
`settings['filled_metals']` is a new option for Palace, used for volume meshing of conductors instead of placing a surface impedance onto the side walls. This gives more accurate conductor loss at **low** frequency, where the skin depth is no longer small compared to conductor cross section. 

Note that the new volume meshing option is **not** the recommended default for Palace: volume meshing requires more RAM and simulation time, and will become inaccurate at higher frequencies, unless you really mesh into skin effect. See the new [`inductor_L6n2_filledmetals_passivation3D`](../more_examples/measured_vs_simulated/inductor_L6n2_filledmetals_passivation3D) example for a comparison of conductor volume mesh against surface-impedance modeling at several mesh sizes, checked against measurement.

`settings['adaptive_mesh_conformal']` is a new experimental option (default `False`) to use conformal AMR mesh refinement instead of Palace's default nonconformal (hanging-node) refinement. From the testcases tried so far, this gave good convergence behaviour, with agressive increase in mesh cell count. For the D-band balun mesh convergence testcase, with only 2 iterations, this reached a similar result as the default non-conformal AMR after 4 iterations, with simulation time cut in half.

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
