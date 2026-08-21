# Change list 

This is an (incomplete) list of changes and new features.

## 21-August-2026
Allowed settings['air_around'] to be 0 on one or more sides, placing the simulation boundary flush with the dielectric/metal stack there instead of requiring a nonzero air gap on all six sides. Boundary faces are now classified by exterior geometry rather than by the airbox volume's own face loop, which broke down once a zero margin merged the airbox's internal cavity into its outer loop. Verified against the previous nonzero-margin behavior (identical config.json output), against 1- and 2-sided zero-margin cases (correct PEC/ABC/PMC separation), and by an actual Palace run.

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
