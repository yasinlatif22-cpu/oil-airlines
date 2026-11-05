"""Convert data/raw/*.csv into the canonical processed files and print a data-quality report.  python ingest.py"""
from pathlib import Path

import numpy as np
import pandas as pd


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
    air = canonical(pd.read_csv(raw / "airlines.csv"))
    air["mktcap"] = market_cap(air)
    air[["date", "permno", "ticker", "open", "close", "ret", "div", "mktcap"]].to_csv(out / "stocks.csv", index=False)
    etf = canonical(pd.read_csv(raw / "etfs.csv"), names)
    etf[["date", "ticker", "open", "close", "ret", "div"]].to_csv(out / "etf.csv", index=False)
    ff = pd.read_csv(raw / "ff_daily.csv")
    ff[["date", "rf", "mktrf"]].to_csv(out / "ff_daily.csv", index=False)

    print("\nairline universe (point-in-time, CRSP SIC 4512): names per year")
    print(air.groupby(air.date.dt.year).permno.nunique().to_string())
    print("\nnames and dates:")
    print(air.groupby(["permno", "ticker"]).date.agg(["min", "max", "count"]).sort_values("min").to_string())
    print("\nmissing opens (airlines):", int(air.open.isna().sum()), "| missing returns:", int(air.ret.isna().sum()))
    print("ETF rows:", etf.groupby("ticker").date.agg(["min", "max", "count"]).to_string())
    big = air.assign(r=air.ret).query("abs(r) > 0.25")[["date", "ticker", "r"]]
    print("\n|daily return| > 25% (check these are real events, not data errors):\n", big.to_string(index=False) if len(big) else "none")


if __name__ == "__main__":
    main()
