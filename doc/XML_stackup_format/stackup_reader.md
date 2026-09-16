# Reading and Writing Stackup XML Files

This is an API-level guide to the two Python modules that touch stackup XML
files — for a programmer or AI agent that needs to *use* them, not for the
XML format itself (see [`XML_stackup_format.md`](XML_stackup_format.md) and
[`derived_layers.md`](derived_layers.md) for that). They are deliberately
separate modules with different jobs:

| | `util_stackup_reader.py` | `stackup_writer.py` |
|---|---|---|
| Lives in | `gds2palace_ihp_sg13g2/workflow/gds2palace/` | `setupEM/src/setupEM/` |
| Used by | the whole gds2palace/openEMS simulation pipeline | setupEM's GUI Stackup Editor only |
| Works at | a parsed, resolved object model (`stackup_material`, `dielectric_layer`, `metal_layer`, ...) | the raw `xml.etree.ElementTree` tree itself |
| Direction | read-only | load, edit, save, validate |
| On a bad file | prints an error and calls `exit(1)` | returns a list of problem strings from `validate_stackup()` |

Both duplicate elsewhere in this workspace and are **not kept in sync
automatically** — see "Duplicated copies" at the end of each chapter.

## Chapter 1: `util_stackup_reader.py` (gds2palace's reader)

### Quick start

```python
from gds2palace import stackup_reader

materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate("SG13G2_200um.xml")

metal = metals_list.getbylayernumber(134)      # TopMetal2, by GDS layer number
print(metal.name, metal.zmin, metal.zmax, metal.thickness, metal.is_via)

material = materials_list.get_by_name(metal.material)
print(material.sigma)                          # conductivity, S/m
```

### What `read_substrate(XML_filename, variable_overrides=None)` actually does

It parses the XML, then hands off to `parse_substrate()` (the same function,
split out so a caller that already holds a parsed tree in memory — e.g. a
live-preview GUI re-deriving after every edit — can skip the disk round
trip). In order:

1. Reads `<Variables>`, applies `variable_overrides` (see below), resolves
   every `"="`-expression.
2. Builds `materials_list` from `<Material>` — auto-adds a built-in `AIR`
   dielectric material if the file doesn't define its own.
3. Builds `dielectrics_list` from `<Dielectric>`, resolves every
   `Reference`/`ReferenceEdge` (explicit or auto-assigned from legacy
   file-order stacking) into absolute `zmin`/`zmax`.
4. Builds `metals_list` from `<Layer>`, resolves its `Reference`s the same
   way, sorts by `zmin`, and works out each layer's `.above`/`.below`
   neighbors.
5. Reads `<DerivedLayers>` (if present) into `metals_list.derived_layers` —
   **definitions only**. The actual boolean-op geometry is computed later,
   by `gds_reader.read_gds()` (`resolve_derived_layers()`), not here.
6. Applies legacy `<Substrate Offset="...">` if present (mutually exclusive
   with any Layer using `Reference`).
7. Registers which metals sit inside which dielectric (`dielectric.metals_inside`).

By the time `read_substrate()` returns, **all Reference/offset resolution is
already done** — every returned object's `.zmin`/`.zmax` is a plain,
absolute `float`. You never need to call `.resolve()` yourself.

### The three return values (plus one attached extra)

**`materials_list`** (`stackup_materials_list`)
- `.materials` — list of `stackup_material`, each with `.name`, `.type`
  (`"CONDUCTOR"`/`"DIELECTRIC"`/etc., upper-cased), `.eps`, `.tand`,
  `.sigma`, `.Rs`, `.density`, `.color`, `.thermalcond`, `.thermaltable`
  (a `thermal_table` or `None`).
- `.eps_max` — highest permittivity across all materials (for solver setup).
- `.get_by_name(name)` — case-insensitive lookup, `None` if not found.

**`dielectrics_list`** (`dielectric_layers_list`)
- `.dielectrics` — list of `dielectric_layer`, each with `.name`,
  `.material`, `.zmin`/`.zmax`/`.thickness` (resolved floats),
  `.is_top`/`.is_bottom`, `.gdsboundary` (int or `None`, from `Boundary=`),
  `.metals_inside` (list of `metal_layer`).
- `.get_by_name(name)`, `.get_boundary_layers()` (list of int, feeds
  `gds_reader.read_gds()`'s `gds_boundary_layers=`).

**`metals_list`** (`metal_layers_list`)
- `.metals` — list of `metal_layer`, each with `.name`, `.layernum`
  (**a string** — see gotchas), `.type`, `.material`, `.zmin`/`.zmax`/`.thickness`,
  `.is_via`/`.is_metal`/`.is_dielectric`/`.is_sheet`, `.above`/`.below`
  (lists of neighboring `metal_layer`).
- `.getbylayernumber(134)` / `.getallbylayernumber(134)` — takes a plain
  `int`, handles the string comparison for you.
- `.getbylayername("TopMetal1")`, `.getlayernumbers()` (list of int),
  `.getallplanarmetals()` (conductor/sheet only, no vias), `.orphan_layers`
  (layers with no `.above`/`.below` neighbor at all).
- `.derived_layers` — a `derived_layers_list` (see next).

**`metals_list.derived_layers`** (`derived_layers_list`, always present,
empty if the file has no `<DerivedLayers>`)
- `.derived_layers` — list of `derived_layer`, each with `.name`,
  `.layernum` (**a string**), `.operation` (`"AND"`/`"OR"`/`"XOR"`/`"NOT"`/`"SIZE"`),
  `.operands` (list of int layer numbers), `.oversize`.
- `.getbylayernumber(n)`, `.getlayernumbers()` (list of int).
- `.get_ordered()` — topologically sorts so a derived layer built from
  *another* derived layer processes after its dependency; can `exit(1)` on a
  circular dependency, so prefer `.derived_layers` directly if you only need
  the raw list (e.g. for `_derived_layer_range_is_safe()`-style presence
  checks) and don't need evaluation order.

### `variable_overrides`

Override any `<Variable>` from a script without touching the XML:

```python
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(
    "stackup.xml", variable_overrides={"total_thickness": 500, "thermal_table_choice": "Si_vs_T_IHP"})
```

Values are plain Python `float`/`int`/`str` (not `"="`-expression strings).
Every key **must** name a `<Variable>` already declared in the file's
`<Variables>` section — an override for an undeclared name is a hard error
(`exit(1)`), not a silent no-op, so a typo is caught immediately.

### Gotchas

- **`layernum` is a string, not an int**, on both `metal_layer` and
  `derived_layer` (`resolve_int_attr()` returns `"134"`, not `134`). Always
  go through `getbylayernumber(int)`/`getlayernumbers()` (which do the
  conversion for you) rather than comparing `.layernum` directly, unless you
  explicitly `int()` it first.
- **Errors are `print()` + `exit(1)`, not exceptions.** A malformed stackup
  file (bad expression, circular Reference, unknown `variable_overrides`
  key, ...) terminates the whole process — there is nothing to `except`. A
  long-running caller (a GUI) that needs to survive a bad file has to
  capture stdout and treat any output as failure; see setupEM's
  `setup_common.py` (`contextlib.redirect_stdout` + catching `SystemExit`
  around calls into gds2palace) for the pattern actually used here.
- **`schemaVersion` checking is cosmetic only.** `read_substrate()` calls
  `check_schema_version()`, which just `print()`s a warning if the file
  declares a `schemaVersion` newer than `SUPPORTED_SCHEMA_VERSION` — it
  never blocks parsing or gates which attributes are accepted.
  `parse_substrate()` (the disk-free half) skips this check entirely.
- **`Material="PEC"` is a bypass, not a real material.** `PEC_MATERIAL_NAME`
  ("PEC") is recognized directly on `metal_layer.material` by downstream
  code (`util_simulation_setup.py`/`util_elmer.py`) as an ideal conductor,
  *without* going through `materials_list.get_by_name()` — so
  `materials_list.get_by_name("PEC")` returns `None` even on a layer whose
  `Material="PEC"`, unless the file also happens to define its own
  `<Material Name="PEC">` (whose properties would then be silently ignored
  anyway — see `find_reserved_material_definitions()` in Chapter 2).
- **`AIR` is auto-injected, `PEC` is not.** If the file has no
  `<Material Name="AIR">`, `parse_substrate()` adds one with built-in
  default properties (`DEFAULT_AIR_MATERIAL_ATTRIBUTES`) so
  `materials_list.get_by_name("AIR")` always resolves to *something*. There
  is no equivalent auto-injection for `PEC` — see above.
- **Derived layer *definitions* vs. derived layer *geometry*** —
  `read_substrate()`/`parse_substrate()` only gives you the `<DerivedLayer>`
  declarations (`metals_list.derived_layers`). The actual boolean-op
  polygons only exist once `gds_reader.read_gds()` runs
  `resolve_derived_layers()` against real GDS data — don't expect derived
  layer geometry from the reader alone.
- **`__version__`** (currently `"1.8.0"`) is display-only: it's
  interpolated into `check_schema_version()`'s warning text and into
  min-reader-version XML comments stamped by `stackup_writer.py`, but never
  parsed back or compared by any code. It's still bumped by convention on
  every commit that changes this file (judged by change size, not a fixed
  increment).

### Duplicated copies

`openems_ihp_sg13g2/workflow/modules/` (a sibling repo in the same
multi-repo workspace as this one) carries an **independent copy** of
`util_stackup_reader.py` for the openEMS flow — not shared/symlinked, so a
fix here does not propagate there. Check both if a bug looks like it could
affect both flows.

## Chapter 2: `stackup_writer.py` (setupEM's writer)

This lives in **setupEM only** (`setupEM/src/setupEM/stackup_writer.py`) —
gds2palace's own pipeline only ever *reads* stackup files, so there is no
`stackup_writer.py` under `gds2palace_ihp_sg13g2/workflow/gds2palace/`. It
backs setupEM's GUI Stackup Editor (`stackupEditor.py`) and works directly
on an `xml.etree.ElementTree` tree — a completely different, lower-level
object model than the reader's `stackup_material`/`dielectric_layer`/
`metal_layer` classes. It imports `gds2palace.stackup_reader` only for a
handful of shared constants/version strings (`PEC_MATERIAL_NAME`,
`SUPPORTED_SCHEMA_VERSION`-adjacent logic, `__version__`), not for parsing.

### Load / new / save

```python
from setupEM import stackup_writer

tree = stackup_writer.load_stackup_tree("stackup.xml")   # or new_stackup_tree() for a blank one
root = tree.getroot()

stackup_writer.add_material(root, Name="Copper", Type="Conductor", Conductivity="5.8e7")
stackup_writer.save_stackup_tree(tree, "stackup.xml")
```

`load_stackup_tree()`/`new_stackup_tree()` return a plain `ElementTree`;
every editing function below takes and returns/mutates plain `Element`
objects — there are no reader-style wrapper classes here at all.

### Editing: one `get_*_element` / `add_*` / `remove_*` triplet per section

A consistent pattern across Materials, Dielectrics, Layers, `<Substrate
Offset>`, DerivedLayers, Variables, and Tables/Points:

- `get_materials_element(root)` / `get_dielectrics_element(root)` /
  `get_layers_element(root)` / `get_derived_layers_element(root, create=False)` /
  `get_variables_element(root, create=False)` / `get_tables_element(root, create=False)`
  — structural lookups (the `create=` ones make the section if it's missing).
- `add_material(root, **attrs)` / `add_dielectric(root, index=None, **attrs)` /
  `add_layer(root, **attrs)` / `add_derived_layer(root, **attrs)` /
  `add_variable(root, **attrs)` / `add_table(root, **attrs)` / `add_point(table_element, **attrs)`
  — keyword args become XML attributes (`str()`-converted; `None`/`""` are
  skipped, not written as empty attributes); return the new `Element`.
- `remove_material(root, element)` (and the `remove_*` sibling for every
  section above) — takes the actual `Element` to delete, not a name/index.
- `move_dielectric(root, element, direction)` / `reorder_layers(root, ordered_elements)`
  — Dielectric/Layer order is semantically meaningful (top-to-bottom), so
  these exist for reordering rather than remove+re-add.
- `set_operands(element, layer_numbers)` / `get_operand_layers(element)` —
  a `<DerivedLayer>`'s child `<Operand>` elements, as a plain list of ints.

### Format-version bookkeeping

`required_schema_version(root)` inspects the tree's *actual content*
(any `"="`-expression or `<Variable>` → `"3.1"`; any `Reference`-positioned
Dielectric/Layer or any `<DerivedLayer>` → `"3.0"`; else `"2.0"`) —
independent of whatever `schemaVersion` the file currently declares.

`save_stackup_tree()` calls this on every save and **self-upgrades**
`schemaVersion` if the content now needs a higher one than what's currently
declared (e.g. a Reference added via some path that doesn't already bump it
itself), stamping the matching min-reader-version XML comment
(`stamp_reference_format_comment()`/`stamp_derived_layers_format_comment()`/
`stamp_variables_format_comment()` — these take `stackup_reader.__version__`,
the *reader's* version, as the "you need this version or newer to read this
back" value). This is **one-directional** — it never downgrades
`schemaVersion` back down even if a later edit stops using that version's
feature.

`save_stackup_tree()` also normalizes attribute order on any
Reference-using Dielectric/Layer, re-sorts `<Layer>` entries by resolved
`Zmin` (descending) and `<Table>`/`<Point>` entries by `Temperature`
(ascending), and preserves XML comments throughout (round-trips them via a
comment-preserving parser) — none of that is optional/toggleable.

### Validation

`validate_stackup(root)` returns `list of str` — human-readable problem
descriptions, **empty list if the file is valid**. Checks Variables (missing
`Name`/`Value`, duplicate names, invalid `Type`, bad/circular expressions)
first, since later sections may reference them, then Materials/Dielectrics/
Layers/DerivedLayers/Tables against the rules in `XML_stackup_format.md`.
This never raises/exits — unlike the reader, it's designed to report every
problem it finds back to a GUI, not fail fast on the first one.

`find_reserved_material_definitions(root)` is a separate, non-blocking
companion: returns `list of str` **warnings** (not `validate_stackup()`
errors) for a `<Material Name="PEC">` entry — legal, but its properties are
silently ignored (see Chapter 1's PEC gotcha). `AIR` is deliberately *not*
warned about here, since a user-defined `<Material Name="AIR">` is a normal,
intended override of the reader's built-in default, not a mistake.

### Its own `__version__`

`stackup_writer.py` has its own `__version__` (currently `"1.6.0"`),
**separate from** `util_stackup_reader.__version__` — the two track
different things (this module's own edit/save/validate logic vs. the
reader's parsing capabilities) and are never compared against each other or
read back by any code either; same display-only convention as Chapter 1's.

### Duplicated copies

`openems_ihp_sg13g2/stackup_editor/stackup_writer.py` (in the same
multi-repo workspace as setupEM and gds2palace_ihp_sg13g2) is an
**independent duplicate** of this file (its own `__version__`, its own copy
of every function above) — ports and fixes must be applied to both
manually, there is no automated sync.
