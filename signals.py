"""Oil events and the basket chosen at a signal close. Every function uses data up to and including the signal close only."""
import numpy as np
import pandas as pd


def oil_events(panel, spec):
    """z_t = USO return_t / sd(USO returns t-L .. t-1). Event when |z| >= threshold; side = -sign(USO return)."""
    r = panel.etf["ret"]["USO"]
    sd = r.shift(1).rolling(spec.z_lookback, min_periods=spec.z_lookback).std()
    z = r / sd
    side = np.where(z.abs() >= spec.z_threshold, -np.sign(r), 0).astype(int)
    return pd.DataFrame({"oil_ret": r, "z": z, "side": side}, index=panel.dates)


def capped_weights(w, cap):
    """Proportional weights with each capped at max(cap, 1/N), the excess redistributed proportionally among the uncapped names."""
    w = w / w.sum()
    cap = max(cap, 1.0 / len(w))                      # the cap must be attainable: at least 1/N
    fixed = pd.Series(False, index=w.index)
    for _ in range(len(w)):
        over = (w > cap + 1e-12) & ~fixed
        if not over.any():
            break
        fixed |= over
        w[fixed] = cap
        free = ~fixed
        w[free] = w[free] / w[free].sum() * (1 - cap * fixed.sum())
    return w


def basket(panel, i, spec):
    """Eligible airlines at the close of session i: present in the CRSP SIC 4512 universe that day, market cap >= min_cap and
    price >= min_price at that close. Returns capped weights (empty if fewer than min_names)."""
    cap, px = panel.mktcap.iloc[i], panel.close.iloc[i]
    ok = panel.member.iloc[i].eq(1) & cap.notna() & px.notna() & (cap >= spec.min_cap) & (px >= spec.min_price)
    names = cap.index[ok]
    if len(names) < spec.min_names:
        return pd.Series(dtype=float)
    w = cap[names].astype(float) if spec.weighting == "vw" else pd.Series(1.0, index=names)
    return capped_weights(w, spec.weight_cap)


def hedge_beta(panel, i, w, spec):
    """OLS slope of the fixed-weight basket's daily return on SPY's over the beta_window sessions ending at i, clipped."""
    lo = max(0, i - spec.beta_window + 1)
    r = panel.ret.iloc[lo:i + 1][w.index]
    have = r.notna()
    br = (r.fillna(0.0) * w).sum(axis=1) / (have * w).sum(axis=1).replace(0, np.nan)
    spy = panel.etf["ret"]["SPY"].iloc[lo:i + 1]
    df = pd.concat([br, spy], axis=1, keys=["b", "m"]).dropna()
    if len(df) < 60:
        return np.nan
    b = np.polyfit(df.m, df.b, 1)[0]
    return float(np.clip(b, spec.beta_min, spec.beta_max))
