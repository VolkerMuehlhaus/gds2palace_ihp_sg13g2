# Tests

```
python -m pytest tests                  # everything without meshing the examples, about 1.5 min
python -m pytest tests -m examples      # the model files of the examples, with meshing, about 5 min
```

Needs `pytest` and `scikit-rf` in addition to gds2palace. No Palace run, no gmsh window.
The same two commands run on GitHub for every push and pull request (`.github/workflows/tests.yml`).

## What is tested

| File | Subject |
|---|---|
| `test_gds_reader.py`, `test_reader_fixtures.py` | Polygon repair of the GDS reader, on layouts with awkward hole encodings |
| `test_examples_reader.py` | GDS reader on the shipped examples |
| `test_examples_geometry.py` | gmsh model of the shipped examples, without meshing |
| `test_examples_model.py` | Model files of the shipped examples, with meshing (marker `examples`) |
| `test_port_walls.py`, `test_deembedding.py` | Port walls and calibrated de-embedding |

## The example tests

The examples are run as they are. `example_runner.py` executes a model script with `read_gds()` and
`create_palace()` (or `create_elmer...()`) recorded, the output in a temporary folder and no gmsh
window. A script may build several models; each is checked.

`examples.toml` lists the scripts and what is checked for each:

- all scripts in `workflow/`. One that is not listed fails a test, so a new example cannot be left out.
- from `more_examples/`, one script per distinct structure or feature: several models from one
  script, conformal passivation, transistor ports to a reference sheet, resistors from derived layers,
  conductors solved inside (with and without skin layers), via fill factor, SG13CMOS5L, MIM balun,
  transformer, Elmer thermal. The other mesh, order and conductor model variants of the same layouts
  are left out, and so are the study drivers and the synthesis scripts; `examples.toml` says which.

Three levels, each against its own reference:

1. **Reader** (`reader`). Every layer that `read_gds()` returns must be the shape drawn in the GDSII
   file. The reference is computed in the test from the file. Merged via arrays must cover the drawn
   vias. Differences thinner than 2 nm are rounding and are ignored.
2. **Geometry** (`geometry`). The model is built up to the gmsh geometry. Every layer must be in the
   model with the size that follows from layout and stackup: conductor surface = 2 x area +
   perimeter x thickness, via volume = area x thickness, sheet area, bounding box, port area. The
   number of separate conductor nets in the model must be that of the drawn layout.
3. **Model files** (`model`). The model is meshed. The files must be there, every attribute in
   `config.json` must exist in the mesh with elements, every volume must have a material, and the ports
   must be those of the script. `config.json`, the mesh groups and `port_information.json` are compared
   with `tests/golden/`; the number of tetrahedra may differ by 25 %.

Levels 1 and 2 need no stored results: they fail when the model is wrong. Level 3 fails when the model
files change. If the change is intended, update the stored files and commit them; the diff shows what
changed:

```
UPDATE_GOLDEN=1 python -m pytest tests -m examples
```

## Fixtures in `tests/data`

- `dipole_port_sg13_forPalace_em.gds`, `dipole_model.py`: a slot antenna as exported by KLayout. Its
  ground plane has a strip that reaches into each slot. gds2palace before 0.10.3 lost one of them.
- `keyholes_klayout.gds`, `keyholes_gdspy.gds`, `keyholes.json`: nine shapes with holes, written by
  KLayout and by gdspy. GDSII has no holes; a writer encodes one as a boundary with a slit, and the two
  place the slit differently. `make_keyhole_fixtures.py` writes them.
- `via_bridge.gds`, `via_bridge_model.py`: two lines with via rows within the merging distance.

## Tests of the tests

For each silent failure that was fixed, one test switches the fix off (or alters the data) and
requires the checks to fail: the lost strip (`test_checks_catch_the_lost_strip`), a via array merged
across two lines, and a shape missing in the model (`test_examples_geometry.py`).

## Adding an example

Add the script to `examples.toml`. Start with all three levels, run
`UPDATE_GOLDEN=1 python -m pytest tests -m examples` once and commit the new file in `tests/golden/`.
Leave a level out only with a `note` that says why.
