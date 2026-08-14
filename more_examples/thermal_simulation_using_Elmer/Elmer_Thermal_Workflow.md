# Elmer Thermal Simulation Workflow

This describes how to go from a GDSII layout + stackup XML to a steady-state
thermal (heat conduction) simulation solved by **Elmer FEM**, using
gds2palace. It's a two-step process:

1. **Build the model** — run a Python script that reads your layout and
   stackup, meshes the 3D geometry, and writes Elmer's input files.
2. **Solve it** — run `ElmerSolver` on the generated files.

The rest of this guide walks through that flow using a hand-written model
script, which is the most direct way to see what's actually happening. If you
prefer a GUI instead of writing Python model code, see
[Alternative: using setupThermal](#alternative-using-setupthermal) below —
it drives the same gds2palace functions and produces the same output files.

Worked example files (in this repo):

| File | Role |
|---|---|
| `elmer_thermal_simplest_typicalvalues.py` | Model-building script |
| `SG13_interposer_thermal_typicalvalues.xml` | Stackup with thermal material properties |
| `simplest_with_source.gds` | Layout, including the heat-source/boundary marker layers |

## Prerequisites

- Python with gds2palace and its dependencies (`gdspy`, `gmsh`, `numpy`)
  installed, or the `gds2palace` package folder placed next to your model
  script.
- **Elmer FEM** installed, with `ElmerGrid` and `ElmerSolver` available:
  - Windows: set the `ELMER_HOME` environment variable to your Elmer install
    directory (gds2palace looks for `%ELMER_HOME%\bin\ElmerGrid.exe`).
  - Linux/macOS: have `ElmerGrid` and `ElmerSolver` on your `PATH`.

## 1. Stackup XML: thermal material properties

Every `<Material>` used in a thermal run needs **thermal conductivity** data, this is the only parameter evaluated for steady-state thermal simulation so far. Electrical parameters (as used for S-Parameter simulation) are not evaluated:

```xml
<Material Name="TopMetal2" Type="Conductor" Conductivity="30300000.0"
          Density="2700" ThermalConductivity="237" Color="ff8000"/>
```

- `Density` — kg/m³, optional, passed to Elmer but not used in steady state thermal simulation.
- `ThermalConductivity` — a single value in W/(m·K), for materials whose
  conductivity doesn't change meaningfully with temperature.
- `ThermalConductivityTable` — instead of a single value, point to a
  `<Table>` (defined in a `<Tables>` block) for temperature-dependent
  conductivity, e.g. silicon substrate:

```xml
<Material Name="HighResSubstrate" Type="Semiconductor" Conductivity="0.025"
          ThermalConductivityTable="SiliconThermalCond" Density="2329"/>
...
<Tables>
  <Table Name="SiliconThermalCond">
    <Point Temperature="280" Value="163.00"/>
    <Point Temperature="290" Value="155.20"/>
    ...
  </Table>
</Tables>
```

gds2palace writes this straight through as an Elmer temperature-dependent
material table — no manual `.sif` editing needed for this part.

## 2. Layout: heat sources and constant-temperature boundaries

In the model script, declare where heat enters and leaves the model:

```python
thermal_objects = simulation_setup.all_thermal_objects()
thermal_objects.add_heatsource(simulation_setup.heatsource(
    power=0.65, source_layernum=201, target_layername='TFR'))
thermal_objects.add_consttemp(simulation_setup.constanttemp(
    temp=298, source_layernum=202, target_layername='BACKSIDEGND'))
```

- `source_layernum` — a **GDSII layer number you draw in the layout**,
  purely as a footprint marker (ordinary polygons, datatype 0). It defines
  the *xy* shape of the source/boundary, not its z-position.
- `target_layername` — the name of an existing `<Layer>` from the stackup
  XML. Its z-range becomes the 3D volume the source/boundary is applied to.
  The marker polygon just needs to overlap that layer's footprint in xy.
- `heatsource(power, ...)` — dissipates `power` Watts, distributed as a
  volumetric heat source over that volume. In the example, 0.65 W is applied
  to the `TFR` resistor layer via marker layer 201.
- `constanttemp(temp, ...)` — fixes that volume's temperature (Kelvin),
  acting as a heat sink/reference boundary. In the example, layer 202 pins
  the `BACKSIDEGND` layer to 298 K (25 °C) — a typical backside heatsink
  boundary.

Both marker layers (201 and 202 here) must actually be drawn as polygons
in the GDSII file, in the cell you're reading (`cellname` in the script) —
gds2palace only picks up what's physically there.

Target layer for **heat sources** must be **volumes** with non-zero thickness, i.e. Zmax 
value larger than Zmin.

Target layer for **constant temperature boundaries** is usually a **sheet** layer with zero thickness, i.e. Zmax=Zmin. This is the layer type also defined for sheet resistors in S-Parameter simulation. If the target layer has finite thickness with Zmax different from Zmin, **two** constant temperature boundaries will be created, one at Zmax and the other at Zmin of that target layer.


## 3. Model script settings

Key `settings` for a thermal run (see `elmer_thermal_simplest_typicalvalues.py`):

```python
settings['unit']              = 1e-6   # geometry is in microns
settings['margin']            = 100    # air margin around the layout, in microns
settings['refined_cellsize']  = 5      # extra-fine mesh near heat sources
settings['meshsize_max']      = 100    # coarsest mesh size, in microns
settings['elmer_thermal']     = True   # this is what selects the thermal flow
```

Also set as usual: `gds_filename`, `XML_filename`, `cellname`,
`preprocess_gds`, `merge_polygon_size`, and `thermal_objects` (from step 2).

Output goes to an `elmer_model/` folder created next to the script.

### Optional: skip the interactive mesh preview

By default, gmsh opens an interactive 3D viewer after meshing so you can
inspect the geometry before continuing — closing that window lets the script
proceed. For unattended/batch runs, set:

```python
settings['no_gui'] = True
```

## 4. Run the script

```
python elmer_thermal_simplest_typicalvalues.py
```

This reads the layout and stackup, builds and meshes the 3D geometry, shows
the gmsh preview (unless `no_gui` is set — close the window to continue), and
then automatically converts the mesh to Elmer's native format via
`ElmerGrid`.

### Output files (in `elmer_model/`)

| File | What it is |
|---|---|
| `<basename>.msh` | Intermediate gmsh mesh |
| `mesh/` | Elmer-native mesh (produced by `ElmerGrid`) |
| `case.sif` | Elmer Solver Input File: steady-state Heat Equation, materials, body (volume) definitions, the heat source as a volumetric Body Force, and the constant-temperature Boundary Condition |
| `ELMERSOLVER_STARTINFO` | Tells `ElmerSolver` to use `case.sif` |

It's worth a quick look at the generated `case.sif` before solving,
especially the first time you use a new stackup — it's plain text and easy
to sanity-check (materials, body forces, boundary conditions).

## 5. Run ElmerSolver

gds2palace does **not** launch the solver — run it yourself from the output
directory:

```
cd elmer_model
ElmerSolver
```

`ElmerSolver` finds `case.sif` automatically via `ELMERSOLVER_STARTINFO`.

If you set `settings['ELMER_MPI_THREADS']` to more than 1 in the model
script, gds2palace also partitions the mesh for you (`ElmerGrid ... -metiskway`);
in that case run `ElmerSolver_mpi` instead (with your MPI launcher of choice)
rather than the single-threaded `ElmerSolver`.

### Results

- `thermal_results.vtu` — full 3D temperature field, open in ParaView.
- `thermal_results.dat` — quick min/max temperature summary (plain text).

Both appear in the `elmer_model/` output directory once `ElmerSolver`
finishes.

## Alternative: using setupThermal

[setupThermal](https://github.com/VolkerMuehlhaus/setupEM) is a desktop GUI
(from the sibling `setupEM` project) that drives this exact same flow without
writing a Python script by hand:

- **Input Files tab** — pick your GDSII layout and stackup XML, same as
  `gds_filename`/`XML_filename` above.
- **Thermal objects tab** — add one row per heat source or constant-temperature
  boundary: GDSII source layer, target stackup layer name, and power (W) or
  temperature (K). This is the GUI equivalent of the
  `thermal_objects.add_heatsource(...)` / `add_consttemp(...)` calls in
  step 2 above.
- **Create Model tab**:
  - **"⚙️ Create mesh and simulation settings file"** generates the
    equivalent Python model script from your GUI settings, then runs it —
    same mesh, `case.sif`, and `ELMERSOLVER_STARTINFO` as described above.
  - **"▶️ Start Simulation"** launches `ElmerSolver` directly from the app,
    streaming its output into the on-screen log — no separate terminal step.
- The **Model** tab shows the generated Python code, so you can inspect or
  export it if you'd rather take over from there manually (e.g. to hand-tune
  something the GUI doesn't expose).

Everything in the sections above about material thermal properties, marker
layers, and output files applies the same way whether the model was built by
hand or through setupThermal — it's the same gds2palace functions underneath.
