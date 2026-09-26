# Choosing a mesh for your Palace simulation

If you're not sure how fine to mesh your gds2palace model, or whether FEM order or adaptive mesh refinement (AMR) matters, this page collects six mesh studies on real IHP structures. Each study reruns one layout at several mesh settings and tells, step by step, what changed, what it cost and which setting we'd use for that structure.

These are six structures at six frequency ranges. Their numbers won't transfer directly to your design, but the patterns below showed up often enough to be worth knowing.

## The six studies

| Study | Structure | Finest feature | Working point found |
|---|---|---|---|
| [Spiral inductor](mesh_convergence_inductor/README.md) | 4-turn spiral, 0–50 GHz | 5 µm trace / gap | 2 µm (Q within 2%); 5 µm is enough for L alone |
| [Transformer](mesh_convergence_transformer/README.md) | 1:1 coil pair, 30 GHz | 2 µm traces | 2 µm for L and k; Q not converged even with AMR |
| [D-band balun](mesh_convergence_D-band_balun/README.md) | edge-coupled lines, 120–160 GHz | 2 µm gap | 2 µm for design, 1 µm for final numbers |
| [2:1 edge-coupled balun](mesh_convergence_balun2x1/README.md) | 4 coupled lines, 1–50 GHz | 2 µm gap | 2 µm; 5 µm is too coarse |
| [MIM-loaded balun](mesh_convergence_balun_mim/README.md) | complete balun with MIM caps, 17–22 GHz | via / MIM detail | 2 µm for loss and balance, 1 µm for the match |
| [MOM capacitor](mesh_convergence_mom_cmos5l/README.md) | interdigitated fingers, SG13CMOS5L, 1 GHz | 0.16 µm fingers | 0.1 µm at order 3 |

## What we saw across these studies

- **What you look at decides how fine you must mesh.** Inductance, coupling and balun amplitude/phase balance settled on coarse meshes in every study that reported them. Q factor, capacitance and the frequency position of a resonance or match null needed the finest meshes, and in the transformer Q had not settled even at the largest model we ran. Check the quantity you'll actually use, not just one S-parameter summary number.
- **Don't let the cell size exceed the smallest gap or trace.** Where it did (5 µm cells on a 2 µm gap or 2 µm traces), results were clearly worst, or the solver crashed.
- **FEM order 1 was far off wherever we tried it.** In the inductor and the 2:1 balun it underestimated Q by 10–26% and shifted the response in frequency. Refining the mesh reduced that error but didn't close it, and an order-2 run on a coarse mesh was more accurate for about the same time. Order 1 is fine for checking ports and setup, not for numbers.
- **Order 3 is a useful cross-check, and sometimes the better deal.** For the MOM capacitor it reached a given accuracy faster than refining the order-2 mesh, and order 2 stayed 1.2% high even at the finest mesh. In the D-band balun it confirmed the finest order-2 result.
- **AMR confirmed the finest uniform mesh, but never at lower cost.** In all five studies that ran it, its S-parameters landed close to the finest uniform run (Max|ΔS| 0.002–0.024), at 1.2–20× that run's time. In the 2:1 balun it was less accurate on Q than a cheaper uniform mesh, and in the transformer it was still changing when its iteration budget ran out. Use it as a second opinion, not as a shortcut.
- **When in doubt, run two meshes and compare the quantity you care about.** If it doesn't change much between a medium and a fine mesh, you're probably fine. If it does, go finer, or try order 3.

## A note on Palace's own error indicator

These reports don't show Palace's internal `error-indicators.csv` Norm/Max values. That indicator is a relative, energy-normalized FEM residual, a different kind of number from the mesh-quality or Delta-S criteria you may know from other solvers (HFSS, CST), and Palace's own documentation notes it "is not a strict relative-error bound for every derived quantity such as S-parameters." The studies judge convergence from the simulated quantities themselves (L, Q, k, balance, capacitance) and from `Max|ΔS|` instead.

For how these studies were produced, and how to run one on a new layout, see [AGENTS.md](AGENTS.md).
