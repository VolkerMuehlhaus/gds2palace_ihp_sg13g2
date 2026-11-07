"""Direct solve (chk_<coil>) against the fast sweep on the same mesh, and the diagnostic runs against the sweeps."""
import sys
import numpy as np
import analyze
import trend

def check(coil):
    f0, y0 = analyze.read_y(f"chk_{coil}")
    f1, y1 = analyze.read_y(f"s_{coil}_g10_float")
    a, b = analyze.values(f0, y0), analyze.values(f1, y1)
    print(f"{coil}: sweep against direct solve, relative difference in %")
    print("   f GHz      L_diff direct      L %     R %     Q %   Y_cm %")
    for i, freq in enumerate(f0):
        k = int(np.argmin(np.abs(f1 - freq)))
        rel = lambda key: 100 * (b[key][k] - a[key][i]) / abs(a[key][i])
        print(f"{freq/1e9:8.2f} {a['L_diff'][i]*1e9:14.4f} {rel('L_diff'):8.3f} {rel('R_diff'):7.3f} {rel('Q_diff'):7.3f}"
              f" {100*abs(b['y_cm'][k]-a['y_cm'][i])/abs(a['y_cm'][i]):8.3f}")

def diag(coil):
    names = [f"s_{coil}_g150_float", f"s_{coil}_g10_float", f"d_{coil}_g10_slot", f"s_{coil}_g30_float", f"s_{coil}_g30_tied"]
    print(f"{'run':24s}" + "".join(f"{c:>8s}" for c in trend.COLUMNS))
    for name in names:
        v = trend.row(name)
        print(f"{name:24s}" + "".join(f"{v[c]:8.3f}" if v[c] < 100 else f"{v[c]:8.0f}" for c in trend.COLUMNS))

for c in sys.argv[1:]:
    check(c); diag(c)
