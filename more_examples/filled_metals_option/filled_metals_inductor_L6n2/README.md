# Stackup and Conductor Model Study: L6n2 Inductor vs. Measurement (IHP SG13G2)

This study evaluates the benefit of two error sources:

## Conductors modeled as filled volumes ("Mesh inside") 
In the User's Guide, there is a detailed analysis on the limitations of the "surface impedance sheet" loss model that gds2palace uses for modelling conductor layers. Here, we investigate the benefit of using a volume mesh ("solve inside") with conductivity for such cases. Be aware that this is not a universal solution, because it becomes inaccurate when skin effect is much smaller than mesh cell size. Both loss models have their use cases.

## True conformal passivation
The stackup used so far covers TopMetal2 with another thick layer of SiO2 plus Passivation. This is efficient for simulation, but we can do better now: a recent extension of the stackup file format now offers "derived layers", so that we can now create a stackup that models the true "conformal" shape of dielectrics above TopMetal2. We will see that this is indeed useful to match the measured fSRF of the testcase, with more accurate prediction of the true capacitance between the sidewalls of closely spaced TopMetal2 traces.

Conformal passivation according to process specification:
![(Passivation)](results/plots/conformal_passivation.png)

Simple planarized stackup used so far:
![(Passivation)](results/plots/planar_stackup.png)


## The details of this study:

- **Model:** `L6n2_with_ports.gds` (cell `L_6n2`), 2 via ports from Metal1 to TopMetal1, Z0 = 50 Ω
- **Solver:** AWS Palace (FEM), order 2, ABC boundaries, 100 µm margin, 50 µm air around
- **Sweep:** 0–14 GHz in 0.1 GHz steps, using Palace's adaptive frequency sweep. 14 GHz is about 1.2x the measured self-resonant frequency (SRF). All S-parameters are de-embedded, so the port inductance is removed.
- **Measurement:** `meas_L5_6n2_THRU_deemb.S2P`, already de-embedded, 100 MHz–50 GHz. The measured differential SRF is **11.07 GHz**.
- **Execution:** Simulated on `hpz2` with Palace built by Spack, using 16 of 32 cores and up to 109 GB RAM. The 12 jobs ran one after another.

## 0. Layout

![L6n2 layout with port positions labeled, IHP SG13G2 pixel-accurate colors (KLayout)](results/plots/layout_labeled.png)

The inductor is a 4-turn octagonal spiral on TopMetal2. It is about 257 × 352 µm in size. Where the turns cross each other, the path drops down to TopMetal1 through TopVia2. Each crossing uses an array of vias, 128 vias in total. This is normal IHP practice for crossings that carry current. The two leads (`L_A` and `L_B` in the GDS) end at the via ports **P1** and **P2** at the bottom.

## 1. Method

We varied three things and kept everything else the same. This gives 2 × 2 × 3 = 12 runs.

| What we varied | Options |
|---|---|
| Stackup | `SG13G2_200um.xml` ("planar": TopMetal2 sits inside a flat block of SiO2, with Passivation on top) or `SG13G2_200um_3D_passivation.xml` ("conformal": the passivation follows the shape of the metal) |
| Conductor model | Surface impedance (the default, metal is hollow) or `filled_metals=True` (metal is a solid volume, like "solve inside" in HFSS) |
| Mesh | `refined_cellsize` = 5, 2 or 1 µm |

The model files are named `palace_L6n2_<stackup>_<model>_<mesh>um.py`. For the differential values we use `Zdiff = Z11 - Z12 - Z21 + Z22`. From that we get `Ldiff = Im(Zdiff)/ω` and `Qdiff = Im(Zdiff)/Re(Zdiff)`. This is the same method as in `filled_metals_inductor_L2n0` and `mesh_convergence_inductor`.

## 2. Simulation cost

| Stackup | Conductor model | Mesh | DOF | Mesh elements | Solve time | Peak RAM |
|---|---|---:|---:|---:|---:|---:|
| Planar | Surface | 5 µm | 332,044 | 47,959 | 8m 26s | 5.57 GB |
| Planar | Surface | 2 µm | 949,350 | 135,689 | 21m 1s | 13.88 GB |
| Planar | Surface | 1 µm | 1,888,810 | 266,551 | 36m 9s | 28.27 GB |
| Planar | filled_metals | 5 µm | 391,354 | 61,697 | 7m 42s | 6.54 GB |
| Planar | filled_metals | 2 µm | 1,147,416 | 180,848 | 19m 5s | 17.77 GB |
| Planar | filled_metals | 1 µm | 2,410,314 | 379,819 | 45m 40s | 35.86 GB |
| Conformal | Surface | 5 µm | 497,856 | 74,189 | 14m 45s | 7.74 GB |
| Conformal | Surface | 2 µm | 1,231,934 | 180,416 | 27m 24s | 17.78 GB |
| Conformal | Surface | 1 µm | 2,339,478 | 337,898 | 1h 3m 26s | 34.96 GB |
| Conformal | filled_metals | 5 µm | 557,146 | 87,924 | 17m 35s | 8.29 GB |
| Conformal | filled_metals | 2 µm | 1,429,384 | 225,477 | 31m 40s | 20.89 GB |
| Conformal | filled_metals | 1 µm | 2,861,190 | 451,199 | **1h 5m 44s** | **42.09 GB** |

The conformal stackup always costs more than the planar one. It adds small SiO2 blocks on the sides of TopMetal2, and these need a finer mesh. We saw the same effect in the `conformal_3D_passivation` balun study.

`filled_metals` also costs more than surface impedance, because the inside of the metal is now meshed too.

The most expensive run (conformal, filled_metals, 1 µm) costs about 4x more than the cheapest one (planar, surface, 5 µm). This is true for time, RAM and DOF.

Full table: [`results/cost_table.csv`](results/cost_table.csv).

## 3. Differential L, Q and R vs. measurement

There is one plot for each combination of stackup and conductor model. Each plot has three panels: L, Q and series R. Each panel shows the three mesh sizes and the measured curve.

L and Q are shown from 0 to 14 GHz. R uses the same frequency range, but its y-axis stops at 12 Ω. Near the SRF, R shoots up to hundreds of Ω, and that would hide the small values at low frequency.

The best match (conformal + filled_metals) is shown first:

![Conformal / filled_metals](results/plots/LQR_conformal_volume.png)
![Planar / Surface impedance](results/plots/LQR_planar_surface.png)
![Planar / filled_metals](results/plots/LQR_planar_volume.png)
![Conformal / Surface impedance](results/plots/LQR_conformal_surface.png)

**The mesh size hardly matters.** In all four plots, the 5, 2 and 1 µm curves are almost on top of each other. The big differences are between the combinations, not between mesh sizes.

**The stackup sets the self-resonant frequency.** With the planar stackup, the simulated SRF is about 10.2 GHz. This is clearly below the measured 11.07 GHz, and it does not change with mesh or conductor model. With the conformal stackup, the SRF is 11.0–11.1 GHz, right where the measurement is. The balun study showed the same thing: you need the right passivation shape to get the resonance right. A finer mesh does not fix it.

**The conductor model sets the Q level, and so also R.** In this frequency range, surface impedance gives a Q that is too high and an R that is too low. You can see this in both surface impedance plots. With `filled_metals`, Q and R move closer to the measurement. With the conformal stackup, they are almost on the measured curve.

**IMPORTANT NOTE: With "solve inside" (filled metals), the mesh has to resolve the skin effect. This gets harder at higher frequencies, where the skin depth becomes much smaller than 1 µm. The results and conclusion in this study are only valid for the frequency range shown.**

**Best match: conformal stackup + filled_metals.** In this plot, L follows the measurement over the whole band, even through the resonance. Q also matches well in peak value and shape. No other combination comes this close.

## 4. Accuracy vs. measurement (finest mesh, 1 µm)

We check L at 0.1, 4 and 8 GHz, and Q at 1, 5 and 9 GHz. All points stay below the measured SRF of 11.07 GHz. Right at the resonance, the error numbers would not mean much. For L, the measured value is interpolated to the exact frequency, because the measured file has no point at exactly 4 GHz.

**Inductance L:**

| Stackup | Conductor model | Freq | L (nH) | L meas (nH) | L err |
|---|---|---:|---:|---:|---:|
| Planar | Surface | 0.1 GHz | 4.97 | 4.94 | +0.5% |
| Planar | Surface | 4 GHz | 5.55 | 5.59 | -0.6% |
| Planar | Surface | 8 GHz | 11.62 | 9.75 | **+19.1%** |
| Planar | filled_metals | 0.1 GHz | 4.88 | 4.94 | -1.1% |
| Planar | filled_metals | 4 GHz | 5.62 | 5.59 | +0.5% |
| Planar | filled_metals | 8 GHz | 11.74 | 9.75 | **+20.4%** |
| Conformal | Surface | 0.1 GHz | 4.97 | 4.94 | +0.5% |
| Conformal | Surface | 4 GHz | 5.42 | 5.59 | -3.1% |
| Conformal | Surface | 8 GHz | 9.50 | 9.75 | -2.6% |
| Conformal | filled_metals | 0.1 GHz | 4.88 | 4.94 | -1.1% |
| Conformal | filled_metals | 4 GHz | 5.48 | 5.59 | -2.0% |
| Conformal | filled_metals | 8 GHz | 9.58 | 9.75 | -1.8% |

**Quality factor Q:**

| Stackup | Conductor model | Freq | Q | Q meas | Q err |
|---|---|---:|---:|---:|---:|
| Planar | Surface | 1 GHz | 7.29 | 6.46 | +12.9% |
| Planar | Surface | 5 GHz | 18.63 | 15.89 | +17.2% |
| Planar | Surface | 9 GHz | 5.80 | 6.93 | -16.4% |
| Planar | filled_metals | 1 GHz | 6.27 | 6.46 | -2.9% |
| Planar | filled_metals | 5 GHz | 14.37 | 15.89 | -9.6% |
| Planar | filled_metals | 9 GHz | 4.46 | 6.93 | -35.7% |
| Conformal | Surface | 1 GHz | 7.29 | 6.46 | +13.0% |
| Conformal | Surface | 5 GHz | 19.58 | 15.89 | +23.2% |
| Conformal | Surface | 9 GHz | 9.10 | 6.93 | +31.3% |
| Conformal | filled_metals | 1 GHz | 6.28 | 6.46 | -2.7% |
| Conformal | filled_metals | 5 GHz | 15.11 | 15.89 | -4.9% |
| Conformal | filled_metals | 9 GHz | 7.08 | 6.93 | +2.2% |

**Average error over the 3 points, finest mesh:**

| Combination | avg\|L err\| (0.1/4/8 GHz) | avg\|Q err\| (1/5/9 GHz) |
|---|---:|---:|
| Planar / Surface | 6.8% | 15.5% |
| Planar / filled_metals | 7.3% | 16.1% |
| Conformal / Surface | 2.1% | 22.5% |
| **Conformal / filled_metals** | **1.6%** | **3.3%** |

With the planar stackup, L is fine at 0.1 and 4 GHz (about 1% error). But at 8 GHz it is about 20% too high. The reason is the low SRF. At 8 GHz the planar model is already getting close to its own resonance, so L rises too early. The real inductor is still further away from its resonance. This is not a mesh or conductor model problem.

With the conformal stackup, the L error stays at 3% or less at all three points.

Conformal with surface impedance gets L right (2.1%), but Q is still much too high (22.5%). The simulation underestimates the loss.

Only conformal with filled_metals gets **both** L and Q right, and by a wide margin.

Full table with all three mesh sizes: [`results/accuracy_vs_measured_table.csv`](results/accuracy_vs_measured_table.csv).

## 5. Conclusion

- **The stackup fixes the resonance, not the mesh.** With the planar stackup, the SRF is about 0.9 GHz too low. Going from 5 µm to 1 µm mesh barely changes this, and neither does the conductor model. The conformal stackup alone closes the gap. The balun study came to the same result.
- **The conductor model fixes Q, not the mesh.** For this inductor, surface impedance gives a Q that is 13–31% too high, with both stackups. `filled_metals` fixes this. It works best together with the conformal stackup. Then the Q error is 2–5% at 1 and 5 GHz, and only 2.2% at 9 GHz.
- **Recommendation: conformal stackup + `filled_metals` at 2 µm.** This is the only combination that gets both L and Q right for this example and frequency range (1.6% L error and 3.3% Q error on average at 1 µm). The 2 µm result (31m 40s, 20.89 GB) is already very close to the 1 µm result (1h 5m 44s, 42.09 GB), so a finer mesh brings little. Compared to the cheapest run (planar, surface, 5 µm: 8m 26s, 5.57 GB), it costs about **4x more time and RAM. But unlike the cheap run, it actually matches the measurement.**
- **If you can only change one thing:** The stackup matters more for L, because it sets the SRF. The conductor model matters more for Q, because it sets the loss. To get both right, you need conformal and filled_metals together. Conformal with surface impedance still has a Q error above 20%.

**IMPORTANT NOTE: With "solve inside" (filled metals), the mesh has to resolve the skin effect. This gets harder at higher frequencies, where the skin depth becomes much smaller than 1 µm. The results here are only valid for the frequency range shown.**

## 6. "Passicut": a cheaper way to model the passivation

Sections 3–5 showed that the conformal stackup gives the right SRF. But it is also the most expensive option in this study: 2.86M DOF, 1h 5m 44s and 42.09 GB at 1 µm. The cost comes from the extra 3D SiO2 shapes on the sides and top of TopMetal2 (`SiO2_above` and `SiO2_sides`, made with an oversize and NOT operation on TopMetal2).

For this inductor, the mesh size was not the limiting factor. The gap is 5.5 µm and the traces are 8 µm wide, so a 5 µm mesh is still fine. So we tried a cheaper approach with a new stackup: **`SG13G2_200um_passicut.xml`**.

This stackup does not add any extra 3D shapes. Instead, it makes the SiO2 layer thinner by the thickness of TopMetal2. Now SiO2 reaches 1.5 µm above the bottom of TopMetal2, with 0.4 µm Passivation on top. This matches the real stackup in the "valleys" between the TopMetal2 traces. We leave out the conformal coating completely.

The idea: the dielectric between the TopMetal2 traces is now mostly correct. What is still missing is the 0.4 µm dielectric on the sides and the coating on top of the traces. But the dielectric between the sidewalls is now much more realistic than in the planar stackup, where TopMetal2 is fully buried in a solid block of SiO2.

This needs no derived layers and no extra mesh refinement. SiO2 just stops partway up the sides of TopMetal2. We kept `filled_metals`, because sections 3–5 showed that it controls Q and R. We only ran 5 µm and 2 µm mesh. 1 µm was not needed, as explained above.

### Cost

| Variant | Mesh | DOF | Mesh elements | Solve time | Peak RAM |
|---|---:|---:|---:|---:|---:|
| Passicut + filled_metals | 5 µm | 397,486 | 62,619 | 9m 18s | 6.39 GB |
| Passicut + filled_metals | 2 µm | 1,445,386 | 227,705 | 26m 55s | 21.86 GB |
| *(for reference)* Conformal + filled_metals | 1 µm | 2,861,190 | 451,199 | 1h 5m 44s | 42.09 GB |
| *(for reference)* Planar + filled_metals | 1 µm | 2,410,314 | 379,819 | 45m 40s | 35.86 GB |

Passicut at 5 µm is **about 7x faster and needs about 6.6x less RAM** than conformal at 1 µm.

### Accuracy vs. measurement

![Passicut workaround vs. previous best/cheapest](results/plots/LQR_passicut_comparison.png)

The passicut curves at 5 µm and 2 µm are almost on top of the conformal 1 µm curve, for L, Q and R. They are clearly better than the planar stackup, which has the wrong SRF.

| Variant | avg\|L err\| (0.1/4/8 GHz) | avg\|Q err\| (1/5/9 GHz) |
|---|---:|---:|
| Conformal + filled_metals, 1 µm *(reference, sections 3–4)* | 1.6% | 3.3% |
| Planar + filled_metals, 1 µm *(reference, sections 3–4)* | 7.3% | 16.1% |
| **Passicut + filled_metals, 5 µm** | **1.4%** | **6.8%** |
| **Passicut + filled_metals, 2 µm** | **2.6%** | **4.6%** |

At 5 µm, passicut gets L even a bit more accurate than conformal at 1 µm (1.4% vs. 1.6%). At 2 µm the L error is 2.6%, mostly from 8 GHz (-4.4%). Both are much better than planar, which is 20% off at 8 GHz.

The Q error of passicut at 5 µm (6.8%) is higher than for conformal, but much lower than for planar. At 2 µm, the Q error drops to 4.6%, which is close to the 3.3% of conformal.

Full tables: [`results/passicut_accuracy_table.csv`](results/passicut_accuracy_table.csv), [`results/passicut_cost_table.csv`](results/passicut_cost_table.csv).

**Passicut gives most of the accuracy of the conformal stackup at a small part of the cost.** It is a simple change to the stackup file, with no extra 3D shapes. For inductors where the mesh size is not the limiting factor, like this one, we recommend passicut + filled_metals at 5 µm instead of the full conformal stackup.

## 7. Where everything lives

The source files for the passicut runs in section 6 are in a different folder, `test_data/filled_metals_inductor_L6n2/`. This includes the model scripts, `SG13G2_200um_passicut.xml`, the mesh and config files, and the raw solver output. Only the de-embedded results and the plots and tables were copied into this study folder.

```
test_data/filled_metals_inductor_L6n2/
├── L6n2_with_ports.gds                          # same layout as the main study
├── SG13G2_200um_passicut.xml                     # section 6 passicut stackup (input)
├── palace_L6n2_passicut_volume_5um.py, _2um.py   # section 6 model scripts
└── palace_model/                                 # section 6 raw solver output (not committed)

more_examples/filled_metals_option/filled_metals_inductor_L6n2/
├── README.md                                    # this report
├── L6n2_with_ports.gds                          # layout (input)
├── SG13G2_200um.xml                              # planar stackup (input)
├── SG13G2_200um_3D_passivation.xml               # conformal stackup (input)
├── meas_L5_6n2_THRU_deemb.S2P                    # measurement (input)
├── palace_L6n2_<stackup>_<model>_<mesh>um.py     # 12 model scripts (sections 1-5)
├── palace_model/                                 # raw solver output (not committed)
└── results/
    ├── analyze_comparison.py                     # makes the plots and tables for sections 1-5
    ├── analyze_passicut.py                        # makes the plot and tables for section 6
    ├── cost_table.csv                            # section 2
    ├── accuracy_vs_measured_table.csv             # section 4, all 3 mesh sizes
    ├── passicut_cost_table.csv                    # section 6
    ├── passicut_accuracy_table.csv                # section 6
    ├── snp/                                      # de-embedded Touchstone files for all runs, plus measured.s2p
    └── plots/
          layout_labeled.png                       # section 0
          LQR_conformal_volume.png, LQR_planar_surface.png
          LQR_planar_volume.png, LQR_conformal_surface.png
          LQR_passicut_comparison.png               # section 6
```

To remake the plots and tables, run these from the `d:\venv\palace` environment:

- `python results/analyze_comparison.py` for sections 1–5. It reads the cost data from `palace_model/` (using `scripts/palace_summary.py`) and the S-parameters from `results/snp/`.
- `python results/analyze_passicut.py` for section 6. It reads the cost data from `test_data/filled_metals_inductor_L6n2/palace_model/`. For comparison, it uses `conformal_volume_1um.s2p` and `planar_volume_1um.s2p`, which are already in `results/snp/`.
