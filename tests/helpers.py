import numpy as np
import pandas as pd

from data_io import build_panel


def hand_market(n=330, s=300, caps=(1e9, 1e9, 1e9, 5e9)):
    """Deterministic market: USO and SPY alternate +/-0.5% / +/-0.4% (so volatility exists), airlines flat at 50 until the event.
    On session s USO jumps +5% (z about 10): an oil-rise event, so the rule shorts airlines at the next open.
    Airlines: open 50 / close 49 on s+1, close 49 through s+5, open 48 on s+6 (the exit open). SPY flat at 100 from s on."""
    idx = pd.bdate_range("2015-01-02", periods=n)
    alt = np.where(np.arange(n) % 2 == 0, 1, -1)
    uso_r = 0.005 * alt; uso_r[s] = 0.05
    spy_r = 0.004 * alt; spy_r[s:] = 0.0
    def series(r, p0=100.0):
        c = p0 * np.cumprod(1 + r); prev = np.r_[p0, c[:-1]]
        return c, prev
    etf = []
    for tk, r in (("USO", uso_r), ("SPY", spy_r)):
        c, prev = series(r)
        etf.append(pd.DataFrame({"date": idx, "ticker": tk, "open": prev, "close": c, "ret": c / prev - 1, "div": 0.0}))
    close = np.full(n, 50.0); close[s + 1:] = 49.0
    opn = np.full(n, 50.0); opn[s + 2:] = 49.0; opn[s + 6] = 48.0; close[s + 6:] = 48.0
    prev = np.r_[50.0, close[:-1]]
    rows = [pd.DataFrame({"date": idx, "permno": 1 + j, "ticker": f"A{j}", "open": opn, "close": close, "ret": close / prev - 1,
                          "div": 0.0, "mktcap": caps[j]}) for j in range(len(caps))]
    return build_panel(pd.concat(rows, ignore_index=True), pd.concat(etf, ignore_index=True)), idx
