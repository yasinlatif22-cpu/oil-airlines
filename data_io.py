"""Canonical panel and a synthetic generator for tests (not market data).

Processed files (written by ingest.py from the licensed CRSP extract; git-ignored):
  stocks.csv  date, permno, ticker, open, close, ret, div, mktcap, member, delist   (open/close split-adjusted, not dividend-adjusted;
              ret = CRSP total close-to-close return including distributions and delisting returns; div = cash per
              split-adjusted share on the ex-date; mktcap in dollars; member = 1 when CRSP recorded SIC 4512 and common-stock
              attributes that day and the stock is not on the exclusion list; delist = 1 on CRSP's delisting day).
  etf.csv     date, ticker, open, close, ret, div   for USO and SPY
  rf.csv      date, rf                                (daily decimal)
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    open: pd.DataFrame        # dates x permno
    close: pd.DataFrame
    ret: pd.DataFrame
    div: pd.DataFrame
    mktcap: pd.DataFrame
    member: pd.DataFrame      # 1 when the row is an eligible universe member that day (point-in-time), else 0
    delist: pd.DataFrame      # 1 on CRSP's delisting day (its return includes the delisting return)
    ticker: dict              # permno -> last ticker seen
    etf: dict                 # field -> DataFrame dates x {USO, SPY}


def build_panel(stocks, etf):
    stocks = stocks.assign(date=pd.to_datetime(stocks.date))
    etf = etf.assign(date=pd.to_datetime(etf.date))
    dates = pd.DatetimeIndex(sorted(etf[etf.ticker == "SPY"].date.unique()))
    stocks = stocks.assign(member=stocks.get("member", 1), delist=stocks.get("delist", 0))
    wide = {k: stocks.pivot_table(index="date", columns="permno", values=k, aggfunc="last").reindex(dates)
            for k in ("open", "close", "ret", "div", "mktcap", "member", "delist")}
    e = {k: etf.pivot_table(index="date", columns="ticker", values=k, aggfunc="last").reindex(dates) for k in ("open", "close", "ret", "div")}
    tick = stocks.sort_values("date").groupby("permno").ticker.last().to_dict()
    return Panel(dates, wide["open"], wide["close"], wide["ret"], wide["div"].fillna(0.0), wide["mktcap"], wide["member"].fillna(0).astype(int),
                 wide["delist"].fillna(0).astype(int), tick, e)


def load_panel(stocks_path="data/processed/stocks.csv", etf_path="data/processed/etf.csv"):
    return build_panel(pd.read_csv(stocks_path), pd.read_csv(etf_path))


def synthetic(seed=0, n=1500, k=6, oil_beta=-0.35, continuation=0.0, start="2010-01-04", delist=None):
    """Synthetic oil, SPY and k airlines. Each airline's daily log return = mkt beta x SPY + oil_beta x oil + noise.
    continuation > 0 plants under-reaction: over the 5 sessions after each oil move, airlines drift by continuation x oil_beta x
    oil move in total, spread evenly. delist=(airline index, session) removes that airline after the session (its last return is
    a -50% delisting return). Returns (stocks, etf) in the canonical long format."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    mkt = rng.normal(0.0003, 0.010, n)
    oil = rng.normal(0.0, 0.020, n) + np.where(rng.random(n) < 0.03, rng.normal(0, 0.06, n), 0.0)
    drift = np.zeros(n)
    for t in range(n):
        drift[t + 1:t + 6] += continuation * oil_beta * oil[t] / 5
    rows, etf = [], []

    def path(lr, p0):
        c = p0 * np.exp(np.cumsum(lr))
        prev = np.r_[p0, c[:-1]]
        o = prev * np.exp(rng.uniform(0.2, 0.6, n) * (np.log(c) - np.log(prev)))
        return o, c, prev

    for name, lr in (("SPY", mkt), ("USO", oil)):
        o, c, prev = path(lr, 100.0)
        etf.append(pd.DataFrame({"date": idx, "ticker": name, "open": o, "close": c, "ret": c / prev - 1, "div": 0.0}))
    for j in range(k):
        lr = rng.uniform(0.9, 1.4) * mkt + oil_beta * oil + drift + rng.normal(0, 0.012, n)
        o, c, prev = path(lr, rng.uniform(20, 80))
        shares = rng.uniform(1e8, 6e8)
        d = pd.DataFrame({"date": idx, "permno": 10000 + j, "ticker": f"AIR{j}", "open": o, "close": c, "ret": c / prev - 1,
                          "div": 0.0, "mktcap": c * shares})
        d["member"], d["delist"] = 1, 0
        if delist and delist[0] == j:
            s = delist[1]
            d.loc[s, "ret"] = -0.5
            d.loc[s, "delist"] = 1
            relist = delist[2] if len(delist) > 2 else None        # CRSP can reuse an identifier later (AMR -> AAL)
            d = pd.concat([d.iloc[: s + 1], d.iloc[relist:]]) if relist else d.iloc[: s + 1]
        rows.append(d)
    return pd.concat(rows, ignore_index=True), pd.concat(etf, ignore_index=True)
