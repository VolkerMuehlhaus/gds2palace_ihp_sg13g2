# IHP stackup files (latest)

These are the current gds2palace stackup files for IHP SG13G2 and SG13CMOS5L. They replace the files in [../../legacy](../../legacy), which are kept only for compatibility with older models. For the XML format itself, see the [XML stackup format description](../../../doc/XML_stackup_format/XML_stackup_format.md).

The files need gds2palace 0.5.0 or newer (September 2026), the first release with both `<Variables>` and the reserved `PEC` material.

| File | Technology | Passivation over top metal | Default total height |
|---|---|---|---:|
| `SG13G2_FEM_200um.xml` | SG13G2 (7 metals) | planar SiO2 + Passivation block over TopMetal2 | 200 µm |
| `SG13G2_FEM_200um_passi3D.xml` | SG13G2 (7 metals) | conformal SiO2 around TopMetal2 (derived layers) | 200 µm |
| `SG13CMOS5L_200um.xml` | SG13CMOS5L (5 metals) | planar SiO2 + Passivation block over TopMetal1 | 200 µm |

"200um" is the total chip height. For SG13G2 this is 180.12 µm substrate below 19.88 µm of EPI + BEOL. The legacy `SG13G2_200um.xml` used a 180 µm substrate, so its total height was 199.88 µm.

## Changes from the legacy stackups

**Parameterized heights (`<Variables>`)**
- `total_thickness`: final chip height. The substrate thickness (`bulk_thickness`) is calculated from it, so the BEOL stays the same and only the substrate changes.
- `air_thickness`: thickness of the air layer above the passivation.
- Layers and dielectrics are positioned relative to each other (`Reference`/`ReferenceEdge`) instead of absolute z values, and `LBE` follows the substrate height automatically.

Using parameters for final chip height and air height replaces several legacy files, see the next section. The `_nosub` stackups are no longer required: for the same use case, reduce the bulk silicon height with a variable override `total_thickness = 25`, see the next section.

**Resistors**
- New sheet resistor layers `RHIGH` (Rs = 1360 Ω), `RPPD` (Rs = 260 Ω) and `RSIL` (Rs = 7 Ω) on top of Activ.
- They are created by derived layers from the drawn PDK layers (GatPoly, resistor marker layers), so no extra drawing is needed in the layout.
- New `REF_FOR_TRANSISTOR` PEC sheet (layer 300) at the same height, as a reference plane for transistor ports (see the [transistor example](../../../more_examples/core_transistor_3port_bce/README.md)).

**Ground layers**
- `SUBGND` is now an ideal conductor sheet (`PEC`) on top of the EPI layer. In the legacy files it was a 3.75 µm thick volume of `LOWLOSS` material filling the EPI layer.
- `BACKSIDEGND` (layer 251) is now a `PEC` sheet at the bottom of the substrate. In legacy `SG13G2_200um.xml` it was a 6.25 µm `LOWLOSS` volume below the substrate; legacy `SG13CMOS5L_200um.xml` had no backside ground at all.
- The `LOWLOSS` material is no longer needed and has been removed.
- In SG13CMOS5L, `SUBGND` moved from GDS layer 210 to 250, the same as SG13G2. Layer 210 was inside the range 201–249 used for port polygons. Layouts that drew SUBGND on layer 210 for the legacy CMOS5L stackup need to move those shapes to layer 250.

**Conformal passivation (`SG13G2_FEM_200um_passi3D.xml` only)**
- The planar SiO2 dielectric ends 1.5 µm above the bottom of TopMetal2 (the "valleys" between TopMetal2 traces), followed by the Passive and AIR layers.
- `SiO2_above_TM2` (layer 900): 1.9 µm of SiO2 on top of TopMetal2 (1.5 µm SiO2 + 0.4 µm passivation, both modelled as SiO2).
- `SiO2_sides_TM2` (layer 901): SiO2 on the TopMetal2 side walls, 0.6 µm wide.
- Both are derived from TopMetal2 automatically (`TM2_oversize` / `TM2_SiO2_sides` derived layers).
- See the [L6n2 inductor study](../../../more_examples/measured_vs_simulated/more_accurate_models_L6n2/README.md) for results and simulation cost compared to the planar stackup.

## Legacy files and their replacement

| Legacy file | Use instead |
|---|---|
| `SG13G2_200um.xml` | `SG13G2_FEM_200um.xml` (substrate 0.12 µm thicker, total height now exactly 200 µm) |
| `SG13G2_100um.xml` | `SG13G2_FEM_200um.xml` with `total_thickness = 100` (substrate 0.12 µm thicker, total height now exactly 100 µm) |
| `SG13CMOS5L_200um.xml` | `SG13CMOS5L_200um.xml` (SUBGND on layer 250 instead of 210) |
| `SG13CMOS5L_300um.xml` | `SG13CMOS5L_200um.xml` with `total_thickness = 300` (identical dielectric heights, SUBGND on layer 250 instead of 210) |
| `SG13CMOS5L_200um_backsideGND.xml` | `SG13CMOS5L_200um.xml` with backside ground drawn on layer 251. The legacy file modelled a 1 µm backside metal slab below the substrate, so all heights differ by 1 µm. SUBGND on layer 250 instead of 210. |
| `SG13G2_nosub.xml`, `SG13CMOS5L_nosub.xml` | `SG13G2_FEM_200um.xml` / `SG13CMOS5L_200um.xml` with `total_thickness = 25`. Not identical, but a similar use case: the legacy files had no silicon at all (BEOL on a 2 µm spacer), while this keeps the 3.75 µm EPI layer on a thin substrate. Do not go below `total_thickness` = 19.88 (SG13G2) or 13.05 (SG13CMOS5L): the substrate thickness would become zero or negative, and the stackup reader does not check this. |
| `pcb_ro4003.xml` | not an IHP stackup, keep using the legacy file |

## Overriding stackup variables in the model code

A model can change any `<Variable>` of the stackup file without editing the XML file. The Python model code passes a dictionary of overrides to the stackup reader:

```python
settings['SubstrateFile'] = 'SG13G2_FEM_200um.xml'
settings['variable_overrides'] = {'total_thickness': 100, 'air_thickness': 300}

...

# ================= read stackup and geometries =================
materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (settings['SubstrateFile'], variable_overrides=settings['variable_overrides'])
```

Without overrides, the dictionary is empty and the values from the XML file are used:

```python
settings['variable_overrides'] = {}
```

How overrides work:
- Each key must be the name of a `<Variable>` defined in the stackup file. An unknown name stops the model with an error, so a typo is not silently ignored.
- The values are plain numbers, not `=` expressions.
- Variables calculated from an overridden variable follow it automatically. For example, overriding `total_thickness` also changes `bulk_thickness` (substrate) and the height of `LBE`.
- Override the base variables (`total_thickness`, `air_thickness`), not the calculated ones like `bulk_thickness`. An override replaces a calculated variable's formula completely.

In setupEM, you don't need to write this code by hand. When you select a stackup file that has variables, setupEM shows an "Override stackup Variables" table with the XML value of each plain variable. Values entered in the "Override value" column are written to `settings['variable_overrides']` in the generated model code.

For parameter sweeps in a script, call `read_substrate()` once per value, for example to compare chip heights:

```python
for total in (100, 200, 300):
    materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(
        'SG13G2_FEM_200um.xml', variable_overrides={'total_thickness': total})
    # ... create and run one model per chip height
```

## Thermal properties (for Elmer thermal simulation)
Every material now has a thermal conductivity; the legacy files had none.

| Material | Thermal conductivity (W/m·K) |
|---|---:|
| Metals (Metal1–5, TopMetal1/2, MIM) | 237 |
| Vias and contacts (Cont, Via1–4, TopVia1/2, Vmim) | 174 |
| Activ | 50 |
| SiO2 | 1 |
| Passive | 0.5 |
| AIR | 0.026 |
| Substrate, EPI | temperature table `Si_vs_T_IHP` (IHP-measured, DOI: 10.1109/EuroSimE.2018.8369872) |