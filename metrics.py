"""Performance statistics from daily total-equity returns."""
import numpy as np
import pandas as pd


def drawdown(r):
    eq = (1 + pd.Series(r).fillna(0.0)).cumprod()
    peak = np.maximum.accumulate(np.r_[1.0, eq.values])[1:]
    return pd.Series(eq.values / peak - 1, index=eq.index)


def perf(r, periods=252):
    r = pd.Series(r).dropna()
    if len(r) < 2 or r.std() == 0:
        return dict(mean_ann_ret=np.nan, cagr=np.nan, vol=np.nan, sharpe=np.nan, max_dd=np.nan)
    return dict(mean_ann_ret=r.mean() * periods, cagr=float((1 + r).prod() ** (periods / len(r)) - 1), vol=r.std() * np.sqrt(periods),
                sharpe=r.mean() / r.std() * np.sqrt(periods), max_dd=float(drawdown(r).min()))


def nw_t(x, lags=5):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.nan
    e = x - x.mean(); s = e @ e / n
    for l in range(1, min(lags, n - 1) + 1):
        s += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(s / n)


def boot_mean_ci(x, B=10000, seed=7):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = [rng.choice(x, len(x)).mean() for _ in range(B)]
    return tuple(np.percentile(m, [2.5, 97.5]))
