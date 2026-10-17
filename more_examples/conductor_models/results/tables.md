# Conductor model study: tables

### inductor

Reference: `mesh_convergence_inductor/results/snp/ind_frame_skin_mesh1.s2p`: R at 1 GHz 2.272, L at 10 GHz 0.7818, peak Q 17.08, f peak Q (GHz) 27

| model | unknowns | minutes | peak_gb | its_per_solve | solves | R at 1 GHz | d R at 1 GHz (%) | L at 10 GHz | d L at 10 GHz (%) | peak Q | d peak Q (%) | f peak Q (GHz) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.43 M | 1.7 | 6.4 | 16.4 | 12 | 1.63 | -28.1 | 0.773 | -1.1 | 21.2 | +24.0 | 24 |
| solve_inside | 0.50 M | 2.2 | 7.4 | 16.5 | 13 | 2.26 | -0.4 | 0.779 | -0.3 | 15.7 | -8.0 | 26 |
| solve_inside_skin | 1.05 M | 5.7 | 14.9 | 17.8 | 13 | 2.27 | -0.3 | 0.78 | -0.2 | 16.6 | -2.6 | 27 |
| solve_inside_skin, 5 um | 0.38 M | 2.1 | 5.7 | 22.7 | 13 | 2.26 | -0.6 | 0.772 | -1.3 | 16.4 | -4.1 | 26.5 |

### transformer

Reference: `mesh_convergence_transformer/results/snp/transformer_skin_mesh1.s5p`: Lp at 30 GHz 0.7526, k at 30 GHz 0.7096, Qp at 30 GHz 9.449, Qs at 30 GHz 9.123, peak Qp 9.479, peak Qs 9.557

| model | unknowns | minutes | peak_gb | its_per_solve | solves | Lp at 30 GHz | d Lp at 30 GHz (%) | k at 30 GHz | d k at 30 GHz (%) | Qp at 30 GHz | d Qp at 30 GHz (%) | Qs at 30 GHz | d Qs at 30 GHz (%) | peak Qp | d peak Qp (%) | peak Qs | d peak Qs (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.31 M | 3.6 | 5.6 | 25.3 | 27 | 0.751 | -0.2 | 0.715 | +0.7 | 12.1 | +28.0 | 11 | +20.5 | 12.3 | +29.3 | 11.6 | +21.4 |
| solve_inside | 0.37 M | 5.3 | 6.2 | 30.4 | 29 | 0.755 | +0.3 | 0.714 | +0.6 | 9.08 | -3.9 | 8.67 | -4.9 | 9.15 | -3.5 | 9.2 | -3.7 |
| solve_inside_skin | 0.69 M | 10.0 | 10.7 | 31.1 | 27 | 0.754 | +0.2 | 0.713 | +0.6 | 9.21 | -2.5 | 8.85 | -3.0 | 9.26 | -2.4 | 9.32 | -2.4 |

### balun2x1

Reference: `mesh_convergence_balun2x1/results/snp/balun2x1_skin_mesh1.s4p`: Lp at 10 GHz 1.183, k at 10 GHz 0.6641, peak Qp 15.47, peak Qs 11.93, peak |Sdd21| (dB) -1.38

| model | unknowns | minutes | peak_gb | its_per_solve | solves | Lp at 10 GHz | d Lp at 10 GHz (%) | k at 10 GHz | d k at 10 GHz (%) | peak Qp | d peak Qp (%) | peak Qs | d peak Qs (%) | peak |Sdd21| (dB) | d peak |Sdd21| (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.84 M | 7.2 | 12.3 | 20.8 | 19 | 1.17 | -0.7 | 0.673 | +1.4 | 18.9 | +21.9 | 14 | +17.7 | -1.22 | +0.16 |
| solve_inside | 1.02 M | 12.1 | 14.8 | 27.1 | 21 | 1.18 | +0.0 | 0.666 | +0.3 | 14.6 | -5.4 | 11.1 | -6.7 | -1.41 | -0.03 |
| solve_inside_skin | 1.68 M | 21.7 | 24.4 | 27.3 | 21 | 1.18 | +0.0 | 0.666 | +0.3 | 15.2 | -1.8 | 11.7 | -1.9 | -1.36 | +0.02 |

### dband_balun

Reference: `mesh_convergence_D-band_balun/results/snp/balun_skin_mesh1.s3p`: IL min (dB) 1.061, IL max (dB) 1.208, S11 null (GHz) 144, max |amp. imbalance| (dB) 0.1284, max |phase imbalance| (deg) 9.543

| model | unknowns | minutes | peak_gb | its_per_solve | solves | IL min (dB) | IL max (dB) | S11 null (GHz) | max |amp. imbalance| (dB) | max |phase imbalance| (deg) | largest IL difference (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.34 M | 1.6 | 5.3 | 23 | 13 | 0.999 | 1.15 | 142 | 0.174 | 9.95 | -0.06 |
| solve_inside | 0.41 M | 2.6 | 6.1 | 32 | 13 | 1.19 | 1.36 | 138 | 0.0763 | 9.51 | +0.15 |
| solve_inside_skin | 0.74 M | 5.5 | 10.8 | 37.4 | 13 | 1.06 | 1.23 | 141 | 0.148 | 10 | +0.02 |

### mim_balun

Reference: `mesh_convergence_balun_mim/results/snp/trans_100diff_to_80se_ports_skin_mesh1.s3p`: IL min (dB) 1.197, IL max (dB) 1.284, worst |Sss11| (dB) -17.71, match null (GHz) 18.6

| model | unknowns | minutes | peak_gb | its_per_solve | solves | IL min (dB) | IL max (dB) | worst |Sss11| (dB) | match null (GHz) | largest IL difference (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.95 M | 12.5 | 12.9 | 22.5 | 13 | 1.18 | 1.31 | -15.9 | 18.1 | -0.02 |
| solve_inside | 1.15 M | 15.6 | 15.9 | 30.6 | 13 | 1.26 | 1.37 | -16.3 | 18.2 | +0.09 |
| solve_inside_skin | 1.66 M | 19.0 | 22.5 | 31.4 | 13 | 1.22 | 1.33 | -16.6 | 18.3 | +0.05 |
| solve_inside_skin, 3 um | 1.14 M | 13.4 | 16.1 | 37.9 | 13 | 1.24 | 1.36 | -16 | 18.1 | +0.08 |

### lines

Line resistance R' (corrected for the losses outside the conductor) divided by R' of the 2D calculation, and the attenuation error against the filled 0.25 um model in dB/mm. Cost of the 300 um line.

| w (um) | model | quantity | 1 GHz | 5 GHz | 10 GHz | 20 GHz | 30 GHz | 50 GHz | 75 GHz | 100 GHz | 150 GHz | unknowns | minutes | peak GB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.01 | surface | R'/R'_2D | 0.399 | 0.453 | 0.554 | 0.698 | 0.748 | 0.778 | 0.801 | 0.820 | 0.846 | 0.33 M | 2.4 | 5.3 |
| | | d alpha (dB/mm) | -0.110 | -0.130 | -0.117 | -0.099 | -0.103 | -0.125 | -0.148 | -0.164 | -0.186 | | | |
| 2.01 | solve_inside | R'/R'_2D | 1.008 | 1.012 | 1.024 | 1.060 | 1.092 | 1.127 | 1.140 | 1.141 | 1.126 | 0.34 M | 2.5 | 5.4 |
| | | d alpha (dB/mm) | +0.002 | +0.003 | +0.007 | +0.018 | +0.031 | +0.046 | +0.053 | +0.052 | +0.040 | | | |
| 2.01 | solve_inside_skin | R'/R'_2D | 1.008 | 1.010 | 1.015 | 1.028 | 1.033 | 1.029 | 1.023 | 1.021 | 1.026 | 0.43 M | 3.4 | 6.3 |
| | | d alpha (dB/mm) | +0.002 | +0.003 | +0.004 | +0.008 | +0.008 | -0.000 | -0.015 | -0.026 | -0.037 | | | |
| 4.5 | surface | R'/R'_2D | 0.617 | 0.637 | 0.671 | 0.753 | 0.793 | 0.827 | 0.851 | 0.869 | 0.892 | 0.33 M | 2.3 | 5.2 |
| | | d alpha (dB/mm) | -0.042 | -0.051 | -0.059 | -0.066 | -0.073 | -0.086 | -0.096 | -0.101 | -0.102 | | | |
| 4.5 | solve_inside | R'/R'_2D | 1.006 | 1.021 | 1.048 | 1.079 | 1.100 | 1.133 | 1.154 | 1.162 | 1.160 | 0.34 M | 2.4 | 5.4 |
| | | d alpha (dB/mm) | +0.001 | +0.003 | +0.007 | +0.013 | +0.017 | +0.028 | +0.039 | +0.049 | +0.064 | | | |
| 4.5 | solve_inside_skin | R'/R'_2D | 1.007 | 1.015 | 1.029 | 1.042 | 1.045 | 1.046 | 1.036 | 1.026 | 1.022 | 0.43 M | 3.3 | 6.3 |
| | | d alpha (dB/mm) | +0.001 | +0.002 | +0.004 | +0.005 | +0.002 | -0.004 | -0.013 | -0.020 | -0.019 | | | |
| 10 | surface | R'/R'_2D | 0.813 | 0.716 | 0.723 | 0.796 | 0.832 | 0.860 | 0.881 | 0.896 | 0.915 | 0.35 M | 2.4 | 5.4 |
| | | d alpha (dB/mm) | -0.013 | -0.029 | -0.039 | -0.044 | -0.049 | -0.054 | -0.056 | -0.053 | -0.044 | | | |
| 10 | solve_inside | R'/R'_2D | 1.003 | 1.029 | 1.063 | 1.103 | 1.124 | 1.138 | 1.136 | 1.129 | 1.111 | 0.36 M | 2.5 | 5.3 |
| | | d alpha (dB/mm) | +0.000 | +0.002 | +0.005 | +0.011 | +0.016 | +0.024 | +0.031 | +0.038 | +0.049 | | | |
| 10 | solve_inside_skin | R'/R'_2D | 1.003 | 1.021 | 1.036 | 1.037 | 1.031 | 1.019 | 1.005 | 0.997 | 1.004 | 0.48 M | 3.9 | 7.0 |
| | | d alpha (dB/mm) | +0.000 | +0.001 | +0.002 | -0.000 | -0.004 | -0.009 | -0.013 | -0.013 | -0.000 | | | |
| 10 | solve_inside_skin, 5 um | R'/R'_2D | 1.018 | 1.062 | 1.067 | 1.041 | 1.030 | 1.024 | 1.017 | 1.016 | 1.025 | 0.22 M | 1.7 | 3.8 |
| | | d alpha (dB/mm) | +0.002 | +0.006 | +0.006 | +0.001 | -0.004 | -0.007 | -0.007 | -0.003 | +0.012 | | | |
| 20 | surface | R'/R'_2D | 0.938 | 0.771 | 0.765 | 0.829 | 0.860 | 0.884 | 0.900 | 0.913 | 0.928 | 0.36 M | 2.5 | 5.3 |
| | | d alpha (dB/mm) | -0.004 | -0.020 | -0.029 | -0.033 | -0.034 | -0.034 | -0.028 | -0.020 | -0.003 | | | |
| 20 | solve_inside | R'/R'_2D | 1.003 | 1.048 | 1.085 | 1.099 | 1.098 | 1.085 | 1.063 | 1.044 | 1.011 | 0.38 M | 2.7 | 5.5 |
| | | d alpha (dB/mm) | +0.000 | +0.002 | +0.004 | +0.006 | +0.008 | +0.012 | +0.017 | +0.021 | +0.028 | | | |
| 20 | solve_inside_skin | R'/R'_2D | 1.002 | 1.029 | 1.036 | 1.004 | 0.986 | 0.966 | 0.955 | 0.953 | 0.977 | 0.52 M | 5.0 | 7.6 |
| | | d alpha (dB/mm) | +0.000 | +0.000 | -0.001 | -0.007 | -0.012 | -0.015 | -0.013 | -0.007 | +0.017 | | | |
| 20 | solve_inside_skin, 5 um | R'/R'_2D | 1.017 | 1.073 | 1.056 | 1.008 | 0.982 | 0.955 | 0.947 | 0.955 | 0.988 | 0.24 M | 2.0 | 4.2 |
| | | d alpha (dB/mm) | +0.001 | +0.004 | +0.001 | -0.007 | -0.012 | -0.017 | -0.014 | -0.005 | +0.023 | | | |

### l6n2

Measured: L at 1 GHz (nH) 5.009, peak Q 15.96, SRF (GHz) 11.07

| model | L at 1 GHz (nH) | peak Q | SRF (GHz) | d L at 1 GHz vs. measured (%) | d peak Q vs. measured (%) | d SRF vs. measured (%) | unknowns | minutes | peak_gb | its_per_solve | solves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v3 study: 'solve_inside', 2 um | 4.96 | 15.2 | 10.9 | -0.9 | -4.6 | -1.6 |  |  |  |  |  |
| v3 study: 'solve_inside', 1 um | 4.96 | 15.4 | 11 | -0.9 | -3.3 | -1.0 |  |  |  |  |  |
| surface | 4.92 | 19.9 | 10.9 | -1.9 | +25.0 | -1.3 | 1.30 M | 19.7 | 18.6 | 35.2 | 12 |
| solve_inside | 4.96 | 15.2 | 10.9 | -0.9 | -4.6 | -1.6 | 1.50 M | 22.9 | 22.2 | 40.2 | 12 |

