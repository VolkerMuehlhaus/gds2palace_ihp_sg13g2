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
- See the [L6n2 inductor study](../../../more_examples/measured_vs_simulated/more_accurate_models_L6n2_v2/README.md) for results and simulation cost compared to the planar stackup.

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
| SiO2 | 1 |
| Passive | 0.5 |
| AIR | 0.026 |
| Substrate, EPI, Activ | temperature table `Si_vs_T_IHP` (IHP-measured, DOI: 10.1109/EuroSimE.2018.8369872) |

Activ is silicon too, with the same table. IHP fitted the table to measured thermal resistances of SiGe HBTs (Korndörfer, Datsuk, Kaynak, "Layout based electro-thermal simulation setup", SiRF 2018): 83 W/m·K at 300 K, lower than undoped silicon (130 to 156 W/m·K) because of the doping. Until gds2palace 0.9.4, Activ had a constant 50 W/m·K without a source. In IHP's npn cells the silicon around each emitter is on Activ.mask (1/20), not Activ, so a thermal model of these cells needs datatype 20 as well (setupThermal's default).

The resistor layers `RHIGH`, `RPPD` and `RSIL` are sheets without thickness and have no thermal properties.

**Heat source targets.** `HEAT_TRANSISTOR` (GDS 320) and `HEAT_RESISTOR` (GDS 321) are target layers for heat sources only. A heat source takes the z range and the material of its target layer, not its shapes. Nothing is drawn on these two GDS layers, so they add no geometry to a model, and EM models are unchanged. Don't draw on GDS layers 320 and 321.

| Target layer | z range | Material | Use for |
|---|---|---|---|
| `HEAT_TRANSISTOR` | top 40 nm of Activ | silicon (`Si_vs_T_IHP`) | transistors |
| `HEAT_RESISTOR` | 0.16 µm above the Activ level | polysilicon, 20 W/m·K | resistors |

A transistor dissipates its heat in a thin layer at the top of the silicon, not in all 0.4 µm of Activ. With `Activ` as the target the heat source is ten times thicker, and the device comes out too cool: for an npn13G2 with 8 emitters and a 750 µm substrate, the thermal resistance at a heat source mesh of 0.125 µm is about 1300 K/W with `Activ` and about 1740 K/W with `HEAT_TRANSISTOR`. With a finer mesh, `HEAT_TRANSISTOR` gives 1832 K/W at 0.0625 µm and 1865 K/W at 0.031 µm, and converges to about 1890 K/W, 8 % above the 1750 K/W of the PDK's transistor model.

A resistor is polysilicon on field oxide. `HEAT_RESISTOR` is that polysilicon body: 0.16 µm thick (gate polysilicon thickness in the SG13G2 process specification), 20 W/m·K (Datsuk, Kaynak, Krupkina, EuroSimE 2018), on the 0.4 µm of oxide that fills the Activ level where no Activ is drawn. With `Activ` as the target, the heat source is silicon that touches the substrate, and the resistor comes out far too cool. The heat source is the resistor body only; the heads under the contacts are not modelled.

Resistor results are not validated yet. For eight sizes of rhigh, rppd and rsil, from 0.5 µm × 0.96 µm to 5 µm × 20 µm, the thermal resistance is 1.5 to 2.5 times the value of the PDK's resistor model, and the ratio grows with the area. 83 to 98 % of the temperature rise is across the oxide below the resistor, so the result follows from the oxide's thickness (0.4 µm) and thermal conductivity (1 W/m·K). The PDK's area term corresponds to 2.4 W/m·K at that thickness. There is no measurement to decide between the two.

Mesh size at the heat source: 0.0625 µm is about 6 % below the converged value for the smallest resistor (0.5 µm × 0.96 µm) and about 3 % below for 0.5 µm × 5 µm. For a resistor 2 µm or wider, 0.125 µm is within about 3 %.

The `PEC` sheets `SUBGND`, `BACKSIDEGND` and `REF_FOR_TRANSISTOR` have no thermal properties. Thermal models ignore them, like the resistor sheets: they have zero thickness and add no thermal volume. A `PEC` sheet can be the target layer of a constant temperature boundary, because the boundary uses only the target layer's z position. For example, this models a heat sink at the chip backside, at the area drawn on layer 202:

```python
thermal_objects.add_consttemp(simulation_setup.constanttemp(temp=298, source_layernum=202, target_layername='BACKSIDEGND'))
```

`PEC` vias and conductor volumes (none in these stackups) use the thermal properties of copper in thermal models: 401 W/m·K at 300 K (CRC Handbook). This also applies to a heat source whose target layer is a `PEC` volume. A heat source needs a target layer with a thickness, so a `PEC` sheet can't be its target.