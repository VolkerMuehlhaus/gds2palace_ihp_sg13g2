# SG13G2 Resistors (Derived Layers)

`palace_resistors_rsil.py` simulates an IHP SG13G2 `Rsil` (silicided
polysilicon) resistor with a nominal value of 50 Ω, recognized purely from
the stackup file rather than being drawn on its own dedicated GDS layer:
`SG13G2_resistors_200um.xml` uses `<DerivedLayers>` boolean operations
(`OR`/`AND`/`NOT`) to build `RSIL`/`RPPD`/`RHIGH` sheet-resistor geometry out
of the poly/implant/contact layers actually present in the GDSII - see
[`../../doc/XML_stackup_format/derived_layers.md`](../../doc/XML_stackup_format/derived_layers.md)
for how that mechanism works in general.

Two via ports (`Metal1` → `Metal2`, layers 201/202) sit at either end of the
resistor.

This is also the reference example for overriding stackup `<Variable>`s
(`total_thickness`, `air_thickness`) from a Python script without editing
the XML - via `stackup_reader.read_substrate(..., variable_overrides=...)` -
see [`../XML_stackup_format_examples`](../XML_stackup_format_examples) for
the full walkthrough of that mechanism, which points back to this script as
its real-world usage example.

## Usage

```bash
source ~/venv/palace/Scripts/activate
python palace_resistors_rsil.py
```

Builds the Palace model under `palace_model/` and writes a `run_sim` script
for handing off to a Linux Palace install (see the top-level
[`README.md`](../../README.md) for the platform split - this workflow
builds model files on any platform, but the Palace solver itself is
Linux-only).

## See also

- [`../../doc/XML_stackup_format/derived_layers.md`](../../doc/XML_stackup_format/derived_layers.md) -
  full reference for `<DerivedLayers>` boolean/resize operations.
- [`../XML_stackup_format_examples`](../XML_stackup_format_examples) -
  tutorial progression through the XML stackup format's features, including
  `variable_overrides` as used here.
- [`../../openems_ihp_sg13g2` repo's `more_examples/resistors_sg13g2`](https://github.com/VolkerMuehlhaus/openems_ihp_sg13g2/tree/main/more_examples/resistors_sg13g2) -
  the openEMS/FDTD counterpart of this same resistor test structure.
