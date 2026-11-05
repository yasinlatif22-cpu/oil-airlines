"""Convert data/raw/*.csv into the canonical processed files and print a data-quality report.  python ingest.py"""
from pathlib import Path

import numpy as np
import pandas as pd



def membership(air, spec):
    """Point-in-time universe flag (common stock with the spec's SIC that day, not excluded) and CRSP's delisting-day flag."""
    common = (air.sharetype.eq("NS") & air.securitytype.eq("EQTY") & air.securitysubtype.eq("COM") & air.usincflg.eq("Y")
              & air.primaryexch.isin(["N", "A", "Q"]))
    member = (common & air.siccd.eq(spec.sic) & ~air.permno.isin(spec.exclude)).astype(int)
    return member, air.dlydelflg.eq("Y").astype(int)

def canonical(raw, etf_names=None):
    r = raw.rename(columns={"dlycaldt": "date"}).sort_values(["permno", "date"]).copy()
    r["date"] = pd.to_datetime(r.date)
    fac = r.dlycumfacpr.where(r.dlycumfacpr > 0)
    r["close"] = r.dlyprc.abs() / fac
    r["open"] = r.dlyopen.abs() / fac
    r["ret"] = r.dlyret
    prev = r.groupby("permno").close.shift(1)
    r["div"] = ((r.dlyret - r.dlyretx).clip(lower=0) * prev).where(lambda s: s > 1e-6, 0.0).fillna(0.0)
    if etf_names:
        r["ticker"] = r.permno.map(etf_names)
    return r


def market_cap(r):
    """dlycap units differ across CRSP releases; choose the scale (x1 or x1000) that makes the median airline cap plausible."""
    cap = r.dlycap.astype(float)
    med = cap.median()
    scale = 1000.0 if med < 1e8 else 1.0
    print(f"market cap: median raw dlycap {med:,.0f}; scale x{scale:g} -> median ${med * scale / 1e9:,.2f}B")
    return cap * scale


def main():
    raw = Path("data/raw")
    out = Path("data/processed"); out.mkdir(parents=True, exist_ok=True)
    import json
    log = json.loads((raw / "extraction_log.json").read_text())
    names = {v: k for k, v in log["etf_permnos"].items()}
    from config import DEFAULT
    air = canonical(pd.read_csv(raw / "airlines.csv"))
    air["mktcap"] = market_cap(air)
    air["member"], air["delist"] = membership(air, DEFAULT)
    print("excluded by name (not scheduled passenger service):", sorted(air[air.permno.isin(DEFAULT.exclude)].ticker.unique()))
    etf = canonical(pd.read_csv(raw / "etfs.csv"), names)
    from data_io import split_at_gaps
    cal = pd.DatetimeIndex(sorted(etf[etf.ticker == "SPY"].date.unique()))
    air = split_at_gaps(air, cal, DEFAULT.gap_sessions)
    print("\nexits (CRSP delisting flag, or the last row before a gap of more than", DEFAULT.gap_sessions, "sessions):")
    print(air[air.delist == 1][["date", "crsp_permno", "permno", "ticker", "close", "ret", "gap_exit"]].to_string(index=False))
    elig = air.member.eq(1) & air.mktcap.ge(DEFAULT.min_cap) & air.close.ge(DEFAULT.min_price)
    for k, g in air.groupby("permno"):
        if g.gap_exit.any():
            d = g[g.gap_exit == 1].date.iloc[0]
            near = g[(g.date <= d)].tail(DEFAULT.hold + 2)
            print(f"  gap exit {g.ticker.iloc[-1]} {d.date()}: basket-eligible in the last {len(near)} sessions before it: "
                  f"{bool(elig.loc[near.index].any())} (if True, a held position could miss an unrecorded post-exchange loss)")
    air[["date", "permno", "crsp_permno", "ticker", "open", "close", "ret", "div", "mktcap", "member", "delist", "gap_exit"]].to_csv(
        out / "stocks.csv", index=False)
    etf[["date", "ticker", "open", "close", "ret", "div"]].to_csv(out / "etf.csv", index=False)
    ff = pd.read_csv(raw / "ff_daily.csv")
    ff[["date", "rf", "mktrf"]].to_csv(out / "ff_daily.csv", index=False)

    print("\nairline universe (point-in-time, CRSP SIC 4512): names per year")
    print(air[air.member == 1].groupby(air.date.dt.year).permno.nunique().to_string())
    print("\nnames and dates:")
    print(air.groupby(["crsp_permno", "permno", "ticker"]).date.agg(["min", "max", "count"]).sort_values("min").to_string())
    print("\nmissing opens (airlines):", int(air.open.isna().sum()), "| missing returns:", int(air.ret.isna().sum()))
    print("ETF rows:", etf.groupby("ticker").date.agg(["min", "max", "count"]).to_string())
    big = air.assign(r=air.ret).query("abs(r) > 0.25")[["date", "ticker", "r"]]
    print("\n|daily return| > 25% (check these are real events, not data errors):\n", big.to_string(index=False) if len(big) else "none")


if __name__ == "__main__":
    main()
