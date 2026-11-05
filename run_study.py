"""Run one evaluation.

  python run_study.py --period dev [--variant primary|hold1|hold10|close_fill|equal_weight]
  python run_study.py --period val --variant primary            # once per variant (recorded in evaluations.json)
  python run_study.py --period holdout --confirm <spec hash>    # once, primary only
  python run_study.py --period val --reproduce --out results_rerun   # re-run of a completed evaluation; never a fresh test
  python run_study.py --period synthetic                        # engine demo on simulated data, not evidence
"""
import argparse
import datetime as dt
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pandas as pd

from config import DEFAULT, VARIANTS
from data_io import build_panel, load_panel, synthetic
from engine import reconcile, run_engine
from metrics import boot_mean_ci, nw_t, perf

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evaluations.json"


def commit():
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return h + ("+uncommitted" if dirty else "")
    except Exception:
        return "unknown"


def recorded(period, variant):
    if not MANIFEST.exists():
        return None
    return next((e for e in json.loads(MANIFEST.read_text())["evaluations"] if e["period"] == period and e["variant"] == variant), None)


def summarize(daily, trades, spec):
    p = perf(daily.ret)
    t = trades.pnl_pct if len(trades) else pd.Series(dtype=float)
    lo, hi = boot_mean_ci(t)
    out = dict(trades=len(trades), mean_trade=t.mean(), trade_t=nw_t(t, 0), trade_ci=(lo, hi), win=(t > 0).mean() if len(t) else float("nan"),
               net_pnl=trades.net_pnl.sum() if len(trades) else 0.0, utilization=daily.in_trade.mean(), **p)
    for side, name in ((1, "after oil falls (long airlines)"), (-1, "after oil rises (short airlines)")):
        s = trades[trades.side == side].pnl_pct if len(trades) else pd.Series(dtype=float)
        out[name] = (len(s), s.mean())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, choices=["dev", "val", "holdout", "synthetic"])
    ap.add_argument("--variant", default="primary", choices=list(VARIANTS))
    ap.add_argument("--confirm", default="")
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args(argv)
    spec = replace(DEFAULT, **VARIANTS[a.variant])
    if a.period == "holdout" and a.variant != "primary":
        raise SystemExit("The holdout is evaluated with the primary specification only.")
    if a.period == "synthetic":
        s, e = synthetic(seed=1, continuation=0.0)
        panel, (first, last) = build_panel(s, e), ("2011-01-01", "2015-12-31")
    else:
        rec = recorded(a.period, a.variant)
        if a.reproduce:
            if rec is None:
                raise SystemExit("Nothing to reproduce: this period/variant is not in evaluations.json.")
            if a.out == "results":
                raise SystemExit("Write reproductions to a separate --out directory.")
        elif rec is not None and a.period != "dev":
            raise SystemExit(f"{a.period}/{a.variant} was already evaluated on {rec['date']}; use --reproduce (not a fresh test).")
        elif a.period == "holdout" and a.confirm != spec.hash():
            raise SystemExit(f"Holdout needs --confirm {spec.hash()} (the frozen specification hash).")
        panel = load_panel()
        first, last = getattr(spec, a.period)
    daily, trades = run_engine(panel, spec, first, last)
    err = reconcile(daily, trades, spec)
    s = summarize(daily, trades, spec)
    out = Path(a.out) / f"{a.period}_{a.variant}"
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "daily.csv"); trades.to_csv(out / "trades.csv", index=False)
    lines = [f"# {a.period} / {a.variant}{' (REPRODUCTION, not a fresh test)' if a.reproduce else ''} | spec {spec.hash()} | code {commit()}",
             f"{daily.index[0].date()} to {daily.index[-1].date()}: {s['trades']} trades, in a trade {s['utilization']:.0%} of days",
             f"mean net per trade {s['mean_trade']:.3%} (t {s['trade_t']:.2f}, 95% bootstrap [{s['trade_ci'][0]:.3%}, {s['trade_ci'][1]:.3%}]), win rate {s['win']:.0%}",
             f"total equity: mean ann. return {s['mean_ann_ret']:.2%}, CAGR {s['cagr']:.2%}, vol {s['vol']:.2%}, Sharpe {s['sharpe']:.2f}, max DD {s['max_dd']:.2%}",
             *(f"{k}: n={v[0]}, mean {v[1]:.3%}" for k, v in s.items() if k.startswith("after")),
             f"reconciliation error ${err:.6f}"]
    (out / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if a.period != "synthetic":
        if not a.reproduce and a.period != "dev":
            m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"evaluations": []}
            m["evaluations"].append(dict(period=a.period, variant=a.variant, spec_hash=spec.hash(), code=commit(),
                                         date=dt.datetime.now().isoformat(timespec="seconds"), headline=f"{s['trades']} trades, Sharpe {s['sharpe']:.2f}"))
            MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
        with open(ROOT / "EXPERIMENTS.md", "a") as f:
            f.write(f"| {dt.date.today()} | {'reproduction' if a.reproduce else a.period} | {a.variant} | {spec.hash()} | "
                    f"{s['trades']} trades, mean {s['mean_trade']:.3%}/trade, Sharpe {s['sharpe']:.2f} | code {commit()} |\n")


if __name__ == "__main__":
    main()
