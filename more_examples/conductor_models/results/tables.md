# Conductor model study: tables

### inductor

Reference: `results/ind_frame_solve_inside_skin_mesh1`: unknowns 2.418e+06, minutes 6.054, peak_gb 34.1, its_per_solve 21.83, solves 12, R at 1 GHz 2.277, L at 10 GHz 0.7842, peak Q 17.6, f peak Q (GHz) 28

| model | unknowns | minutes | peak_gb | its_per_solve | solves | R at 1 GHz | d R at 1 GHz (%) | L at 10 GHz | d L at 10 GHz (%) | peak Q | d peak Q (%) | f peak Q (GHz) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.44 M | 0.8 | 6.8 | 20.2 | 12 | 1.64 | -28.0 | 0.776 | -1.1 | 21.9 | +24.5 | 25 |
| solve_inside | 0.52 M | 1.0 | 7.9 | 20.6 | 13 | 2.27 | -0.4 | 0.781 | -0.4 | 16.1 | -8.3 | 27 |
| solve_inside_skin | 1.07 M | 2.7 | 16 | 23.4 | 13 | 2.27 | -0.3 | 0.783 | -0.2 | 17.2 | -2.4 | 27.5 |
| solve_inside_skin, 5 um | 0.40 M | 0.9 | 6.3 | 27.6 | 12 | 2.26 | -0.7 | 0.776 | -1.1 | 16.7 | -5.3 | 26.5 |

### transformer

Reference: `results/transformer_solve_inside_skin_mesh1`: unknowns 1.446e+06, minutes 9.523, peak_gb 22.9, its_per_solve 29.59, solves 29, Lp at 30 GHz 0.753, k at 30 GHz 0.7098, Qp at 30 GHz 9.527, Qs at 30 GHz 9.212, peak Qp 9.553, peak Qs 9.631

| model | unknowns | minutes | peak_gb | its_per_solve | solves | Lp at 30 GHz | d Lp at 30 GHz (%) | k at 30 GHz | d k at 30 GHz (%) | Qp at 30 GHz | d Qp at 30 GHz (%) | Qs at 30 GHz | d Qs at 30 GHz (%) | peak Qp | d peak Qp (%) | peak Qs | d peak Qs (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.32 M | 1.2 | 5.6 | 22.4 | 27 | 0.751 | -0.2 | 0.715 | +0.7 | 12.2 | +28.4 | 11.1 | +20.9 | 12.4 | +29.5 | 11.7 | +21.8 |
| solve_inside | 0.37 M | 1.9 | 6.4 | 30.7 | 28 | 0.756 | +0.4 | 0.714 | +0.6 | 9.14 | -4.0 | 8.71 | -5.4 | 9.2 | -3.7 | 9.23 | -4.2 |
| solve_inside_skin | 0.67 M | 4.3 | 11 | 33.1 | 29 | 0.755 | +0.2 | 0.714 | +0.6 | 9.27 | -2.7 | 8.9 | -3.4 | 9.31 | -2.5 | 9.37 | -2.7 |

### balun2x1

Reference: `results/balun2x1_solve_inside_skin_mesh1`: unknowns 3.852e+06, minutes 17.71, peak_gb 55.9, its_per_solve 27.37, solves 19, Lp at 10 GHz 1.186, k at 10 GHz 0.665, peak Qp 15.67, peak Qs 12.19, peak |Sdd21| (dB) -1.369

| model | unknowns | minutes | peak_gb | its_per_solve | solves | Lp at 10 GHz | d Lp at 10 GHz (%) | k at 10 GHz | d k at 10 GHz (%) | peak Qp | d peak Qp (%) | peak Qs | d peak Qs (%) | peak |Sdd21| (dB) | d peak |Sdd21| (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.86 M | 2.7 | 12.6 | 21.7 | 18 | 1.18 | -0.6 | 0.674 | +1.4 | 19.1 | +22.0 | 14.3 | +17.6 | -1.21 | +0.16 |
| solve_inside | 1.04 M | 4.7 | 15.7 | 31.5 | 21 | 1.19 | +0.1 | 0.667 | +0.3 | 14.8 | -5.5 | 11.3 | -7.2 | -1.4 | -0.03 |
| solve_inside_skin | 1.70 M | 8.8 | 26.1 | 30.8 | 21 | 1.19 | +0.1 | 0.667 | +0.4 | 15.4 | -1.8 | 12 | -2.0 | -1.34 | +0.03 |

### dband_balun

Reference: `results/dband_balun_solve_inside_skin_mesh1`: unknowns 1.726e+06, minutes 5.468, peak_gb 25.1, its_per_solve 31.31, solves 13, IL min (dB) 1.058, IL max (dB) 1.209, S11 null (GHz) 144, max |amp. imbalance| (dB) 0.119, max |phase imbalance| (deg) 9.553

| model | unknowns | minutes | peak_gb | its_per_solve | solves | IL min (dB) | IL max (dB) | S11 null (GHz) | max |amp. imbalance| (dB) | max |phase imbalance| (deg) | largest IL difference (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.33 M | 0.6 | 5.2 | 22.7 | 13 | 0.998 | 1.15 | 141 | 0.169 | 9.88 | -0.06 |
| solve_inside | 0.40 M | 1.1 | 6.2 | 37.2 | 13 | 1.19 | 1.36 | 137 | 0.0884 | 9.38 | +0.16 |
| solve_inside_skin | 0.71 M | 2.6 | 11.1 | 44.6 | 13 | 1.05 | 1.22 | 140 | 0.121 | 9.98 | +0.02 |

### mim_balun

Reference: `results/mim_balun_solve_inside_skin_mesh1`: unknowns 3.91e+06, minutes 16.39, peak_gb 55.5, its_per_solve 36.77, solves 13, IL min (dB) 1.179, IL max (dB) 1.268, worst |Sss11| (dB) -17.7, match null (GHz) 18.6

| model | unknowns | minutes | peak_gb | its_per_solve | solves | IL min (dB) | IL max (dB) | worst |Sss11| (dB) | match null (GHz) | largest IL difference (dB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| surface | 0.96 M | 3.2 | 13.6 | 26.7 | 13 | 1.17 | 1.29 | -15.9 | 18.1 | -0.02 |
| solve_inside | 1.16 M | 3.7 | 16.7 | 33.9 | 13 | 1.24 | 1.36 | -16.3 | 18.2 | +0.09 |
| solve_inside_skin | 1.67 M | 5.4 | 23.6 | 30.3 | 13 | 1.21 | 1.32 | -16.5 | 18.2 | +0.05 |
| solve_inside_skin, 3 um | 1.16 M | 3.9 | 16.9 | 32.5 | 13 | 1.22 | 1.35 | -16 | 18.1 | +0.08 |

### lines

Line resistance R' (corrected for the losses outside the conductor) divided by R' of the 2D calculation, and the attenuation error against the filled 0.25 um model in dB/mm. Cost of the 300 um line.

| w (um) | model | quantity | 1 GHz | 5 GHz | 10 GHz | 20 GHz | 30 GHz | 50 GHz | 75 GHz | 100 GHz | 150 GHz | unknowns | minutes | peak GB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.01 | surface | R'/R'_2D | 0.399 | 0.452 | 0.554 | 0.697 | 0.747 | 0.776 | 0.799 | 0.818 | 0.844 | 0.32 M | 0.8 | 5.3 |
| | | d alpha (dB/mm) | -0.110 | -0.130 | -0.117 | -0.100 | -0.103 | -0.126 | -0.149 | -0.166 | -0.189 | | | |
| 2.01 | solve_inside | R'/R'_2D | 1.007 | 1.011 | 1.024 | 1.058 | 1.087 | 1.117 | 1.131 | 1.133 | 1.122 | 0.34 M | 0.9 | 5.5 |
| | | d alpha (dB/mm) | +0.002 | +0.003 | +0.006 | +0.017 | +0.028 | +0.042 | +0.047 | +0.046 | +0.037 | | | |
| 2.01 | solve_inside_skin | R'/R'_2D | 1.009 | 1.009 | 1.012 | 1.020 | 1.023 | 1.022 | 1.025 | 1.033 | 1.054 | 0.43 M | 1.2 | 6.5 |
| | | d alpha (dB/mm) | +0.002 | +0.003 | +0.003 | +0.005 | +0.004 | -0.004 | -0.014 | -0.019 | -0.015 | | | |
| 4.5 | surface | R'/R'_2D | 0.617 | 0.637 | 0.672 | 0.753 | 0.794 | 0.827 | 0.852 | 0.869 | 0.892 | 0.32 M | 0.8 | 5.4 |
| | | d alpha (dB/mm) | -0.042 | -0.051 | -0.059 | -0.066 | -0.073 | -0.086 | -0.096 | -0.101 | -0.102 | | | |
| 4.5 | solve_inside | R'/R'_2D | 1.005 | 1.021 | 1.049 | 1.082 | 1.101 | 1.131 | 1.150 | 1.157 | 1.159 | 0.33 M | 0.9 | 5.4 |
| | | d alpha (dB/mm) | +0.001 | +0.003 | +0.008 | +0.014 | +0.017 | +0.026 | +0.037 | +0.046 | +0.063 | | | |
| 4.5 | solve_inside_skin | R'/R'_2D | 1.005 | 1.011 | 1.022 | 1.030 | 1.032 | 1.034 | 1.034 | 1.035 | 1.047 | 0.42 M | 1.4 | 6.7 |
| | | d alpha (dB/mm) | +0.001 | +0.002 | +0.003 | +0.001 | -0.002 | -0.009 | -0.014 | -0.015 | -0.004 | | | |
| 10 | surface | R'/R'_2D | 0.814 | 0.717 | 0.724 | 0.798 | 0.834 | 0.863 | 0.884 | 0.899 | 0.920 | 0.34 M | 0.9 | 5.6 |
| | | d alpha (dB/mm) | -0.013 | -0.029 | -0.039 | -0.044 | -0.048 | -0.054 | -0.055 | -0.052 | -0.043 | | | |
| 10 | solve_inside | R'/R'_2D | 1.004 | 1.033 | 1.066 | 1.101 | 1.118 | 1.128 | 1.126 | 1.119 | 1.105 | 0.36 M | 0.9 | 5.4 |
| | | d alpha (dB/mm) | +0.001 | +0.003 | +0.006 | +0.011 | +0.014 | +0.021 | +0.028 | +0.034 | +0.045 | | | |
| 10 | solve_inside_skin | R'/R'_2D | 1.002 | 1.019 | 1.029 | 1.026 | 1.021 | 1.016 | 1.014 | 1.018 | 1.039 | 0.48 M | 1.4 | 7.3 |
| | | d alpha (dB/mm) | +0.000 | +0.001 | +0.001 | -0.003 | -0.007 | -0.010 | -0.009 | -0.004 | +0.016 | | | |
| 10 | solve_inside_skin, 5 um | R'/R'_2D | 1.018 | 1.059 | 1.061 | 1.036 | 1.024 | 1.011 | 1.001 | 1.000 | 1.006 | 0.21 M | 0.7 | 4.0 |
| | | d alpha (dB/mm) | +0.002 | +0.005 | +0.006 | -0.000 | -0.005 | -0.011 | -0.013 | -0.010 | +0.001 | | | |
| 20 | surface | R'/R'_2D | 0.938 | 0.772 | 0.766 | 0.830 | 0.861 | 0.884 | 0.901 | 0.913 | 0.930 | 0.35 M | 0.9 | 5.4 |
| | | d alpha (dB/mm) | -0.004 | -0.020 | -0.029 | -0.033 | -0.034 | -0.034 | -0.028 | -0.020 | -0.003 | | | |
| 20 | solve_inside | R'/R'_2D | 1.003 | 1.046 | 1.088 | 1.107 | 1.106 | 1.091 | 1.068 | 1.047 | 1.016 | 0.38 M | 1.0 | 5.7 |
| | | d alpha (dB/mm) | +0.000 | +0.002 | +0.004 | +0.007 | +0.009 | +0.013 | +0.018 | +0.022 | +0.029 | | | |
| 20 | solve_inside_skin | R'/R'_2D | 1.001 | 1.025 | 1.032 | 1.010 | 0.993 | 0.976 | 0.973 | 0.981 | 1.011 | 0.52 M | 1.9 | 8.0 |
| | | d alpha (dB/mm) | +0.000 | +0.000 | -0.001 | -0.007 | -0.011 | -0.012 | -0.007 | +0.002 | +0.029 | | | |
| 20 | solve_inside_skin, 5 um | R'/R'_2D | 1.019 | 1.074 | 1.068 | 1.028 | 1.000 | 0.968 | 0.950 | 0.952 | 0.968 | 0.23 M | 0.8 | 4.2 |
| | | d alpha (dB/mm) | +0.001 | +0.004 | +0.002 | -0.004 | -0.009 | -0.014 | -0.014 | -0.007 | +0.013 | | | |

### l6n2

Measured: L at 1 GHz (nH) 5.009, peak Q 15.96, SRF (GHz) 11.07

| model | L at 1 GHz (nH) | peak Q | SRF (GHz) | d L at 1 GHz vs. measured (%) | d peak Q vs. measured (%) | d SRF vs. measured (%) | unknowns | minutes | peak_gb | its_per_solve | solves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v5 study: 'solve_inside', 2 um | 5.02 | 15.6 | 10.8 | +0.3 | -2.2 | -2.1 |  |  |  |  |  |
| v5 study: 'solve_inside', 1 um | 5.02 | 15.8 | 10.9 | +0.3 | -0.7 | -1.6 |  |  |  |  |  |
| surface | 4.97 | 20.6 | 10.9 | -0.7 | +29.2 | -1.9 | 1.36 M | 3.37 | 19.7 | 37.9 | 10 |
| solve_inside | 5.02 | 15.6 | 10.8 | +0.3 | -2.2 | -2.1 | 1.57 M | 4.01 | 23 | 38.1 | 10 |

