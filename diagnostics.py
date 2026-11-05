"""Pre-stated diagnostics (docs/SPEC.md, "Primary outcome and tests") for the recorded primary runs.  python diagnostics.py

Reads results/<period>_primary/{trades,daily}.csv written by run_study.py and the processed panel; changes nothing.
  1. The economic premise: same-day response of the airline basket to USO, controlling for SPY (should be negative).
  2. Results split by oil-rise and oil-fall events (repeated from the run summaries).
  3. Results excluding 2008-09 and 2020 (crisis concentration).
  4. Market beta of the strategy's daily returns.
Also printed, as context and not as a test: all three periods pooled."""
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT
from data_io import load_panel
from metrics import boot_mean_ci, nw_t
from signals import basket

PERIODS = ("dev", "val", "holdout")


def ols_hc(y, X):
    """OLS coefficients and White (HC0) standard errors."""
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    xtx = np.linalg.inv(X.T @ X)
    v = xtx @ (X.T * e ** 2) @ X @ xtx
    return b, np.sqrt(np.diag(v))


def airline_index(panel, spec):
    """Daily return of the rule's basket formed at the previous close (capped value weights), NaN when fewer than 3 names."""
    out = pd.Series(np.nan, index=panel.dates)
    for i in range(1, len(panel.dates)):
        w = basket(panel, i - 1, spec)
        if len(w):
            r = panel.ret.iloc[i][w.index]
            have = r.notna()
            if have.any():
                out.iloc[i] = float((r[have] * w[have]).sum() / w[have].sum())
    return out


def trade_line(label, x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return f"  {label:<34} n={len(x)}"
    lo, hi = boot_mean_ci(x)
    # trades never overlap, so a plain t-statistic (no serial-correlation lags), as in run_study.py
    return f"  {label:<34} n={len(x):>3}  mean {x.mean():+.3%}  t {nw_t(x, 0):+.2f}  95% [{lo:+.3%}, {hi:+.3%}]"


def main(spec=DEFAULT):
    panel = load_panel()
    idx = airline_index(panel, spec)
    uso, spy = panel.etf["ret"]["USO"], panel.etf["ret"]["SPY"]
    lines, pooled = [f"# pre-stated diagnostics | spec {spec.hash()}"], []
    for p in PERIODS:
        d = Path("results") / f"{p}_primary"
        if not (d / "trades.csv").exists():
            lines.append(f"\n## {p}: no recorded run"); continue
        tr = pd.read_csv(d / "trades.csv", parse_dates=["entry_date", "signal_date"])
        daily = pd.read_csv(d / "daily.csv", parse_dates=["date"], index_col="date")
        lo, hi = getattr(spec, p)
        df = pd.concat([idx, uso, spy], axis=1, keys=["air", "uso", "spy"]).loc[lo:hi].dropna()
        b, se = ols_hc(df.air.to_numpy(), df[["uso", "spy"]].to_numpy())
        lines += [f"\n## {p} ({lo} to {hi})",
                  f"1. same-day airline basket return on USO (controlling for SPY), {len(df)} days: "
                  f"USO {b[1]:+.3f} (t {b[1] / se[1]:+.1f}), SPY {b[2]:+.3f}",
                  "2. by event side:",
                  trade_line("all trades", tr.pnl_pct),
                  trade_line("after oil falls (long airlines)", tr[tr.side == 1].pnl_pct),
                  trade_line("after oil rises (short airlines)", tr[tr.side == -1].pnl_pct),
                  "3. excluding entries in 2008, 2009 and 2020:",
                  trade_line("ex-crisis trades", tr[~tr.entry_date.dt.year.isin([2008, 2009, 2020])].pnl_pct)]
        m = pd.concat([daily.ret, spy], axis=1, keys=["s", "m"]).dropna()
        bb, sb = ols_hc(m.s.to_numpy(), m[["m"]].to_numpy())
        lines.append(f"4. strategy daily return on SPY: beta {bb[1]:+.3f} (t {bb[1] / sb[1]:+.1f})")
        lines.append(f"   events per year: {len(tr) / ((pd.Timestamp(hi) - pd.Timestamp(lo)).days / 365.25):.1f}")
        pooled.append(tr.pnl_pct)
    if pooled:
        lines += ["\n## context only (not a test): all periods pooled", trade_line("all trades", pd.concat(pooled))]
    text = "\n".join(lines) + "\n"
    Path("results").mkdir(exist_ok=True)
    (Path("results") / "diagnostics.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
