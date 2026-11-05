"""Dollar ledger for event trades: an airline basket against SPY, held for a fixed number of sessions.

Day by day (session d):
  1. Held positions are marked from the previous close: value x (1 + CRSP total return of d), which includes ex-date
     distributions and delisting returns. A short position's value is negative, so it pays distributions.
  2. If an entry fill is due on d: buy/sell at the open (or close), pay costs, then mark open -> close (a buyer at the open does
     not receive that day's distribution).
  3. If an exit fill is due on d at the open: positions are first moved from the previous close to the open with the gap return
     (open + distribution) / previous close, then closed at the open, with costs. At the close variant they are marked to the
     close first.
  4. Borrow is charged on short market value for each night that follows a close at which a position is held.
  5. At the close, a new order is created if an event occurs while flat; it fills `fill_lag` sessions later.
On CRSP's delisting day a held stock is marked with that day's return (which includes the delisting return) and its value
moves to cash; the event is recorded. This uses the flag, not missing data, because CRSP can resume an identifier after a gap
(AMR's permno later became AAL's; Spirit's after its old shares were cancelled). ingest.py also flags the last row before any
gap longer than spec.gap_sessions and gives later rows a new key (data_io.split_at_gaps). As a fallback, a held stock with no return and no later data also moves to cash; a missing
return with later data and no delisting flag (a halt) counts as 0.
A name in the basket without a fill price on the entry day is dropped and the remaining weights are rescaled; the count is recorded.
Trade P&L reconciles to the change in equity (no interest on cash), or the run fails."""
import numpy as np
import pandas as pd

from signals import basket, hedge_beta, oil_events


class ReconciliationError(AssertionError):
    pass


def run_engine(panel, spec, start, end, fill_lag=1):
    ev = oil_events(panel, spec)
    dates = panel.dates
    lo, hi = dates.searchsorted(pd.Timestamp(start)), dates.searchsorted(pd.Timestamp(end), side="right") - 1
    later = {p: panel.ret[p].last_valid_index() for p in panel.ret.columns}
    ca, cs, br = spec.cost_airline_bps / 1e4, spec.cost_spy_bps / 1e4, spec.borrow_bps / 1e4
    cash, eq_prev = spec.initial_equity, spec.initial_equity
    pos = {}                       # key -> dollar value (permno or "SPY")
    pending, cur = None, None
    rows, trades = [], []

    def close_out(key, value, cost_rate):
        nonlocal cash
        cash += value
        c = cost_rate * abs(value)
        cash -= c
        cur["costs"] += c

    for i in range(lo, hi + 1):
        d = dates[i]
        borrow = 0.0
        exit_now = cur is not None and i == cur["exit_i"]
        # 1-3: mark held positions from the previous close
        for key in list(pos):
            r = panel.etf["ret"]["SPY"].iloc[i] if key == "SPY" else panel.ret[key].iloc[i]
            if exit_now and spec.fill == "open_next":
                o = (panel.etf["open"]["SPY"] if key == "SPY" else panel.open[key]).iloc[i]
                pc = (panel.etf["close"]["SPY"] if key == "SPY" else panel.close[key]).iloc[i - 1]
                dv = (panel.etf["div"]["SPY"] if key == "SPY" else panel.div[key]).iloc[i]
                if np.isfinite(o) and o > 0 and np.isfinite(pc) and pc > 0:     # CRSP delisting rows carry price 0
                    r = (o + dv) / pc - 1
                else:
                    cur["exit_no_open"] += 1          # no opening price: the day's close-to-close return is used instead
            if not np.isfinite(r):
                if key != "SPY" and (later[key] is None or later[key] < d):
                    cash += pos.pop(key)              # left CRSP: last return already included its delisting return
                    cur["delisted"] += 1
                    continue
                r = 0.0                               # trading halt: stale price
            pnl = pos[key] * r
            pos[key] += pnl
            cur["air_pnl" if key != "SPY" else "hedge_pnl"] += pnl
            if key != "SPY" and panel.delist[key].iloc[i] == 1 and not (exit_now and spec.fill == "open_next"):
                cash += pos.pop(key)                  # CRSP delisting day: the return above includes the delisting return
                cur["delisted"] += 1
        if exit_now:
            for key in list(pos):
                close_out(key, pos.pop(key), cs if key == "SPY" else ca)
        if pending and i == pending["due"]:
            p, pending = pending, None
            fp = panel.open if spec.fill == "open_next" else panel.close
            px = fp.iloc[i][p["w"].index]
            w = p["w"][px.notna() & (px > 0)]
            dropped = len(p["w"]) - len(w)
            if len(w) >= spec.min_names:
                w = w / w.sum()
                n = spec.gross_frac * p["equity"]
                cur = dict(signal_date=p["date"], side=p["side"], z=p["z"], oil_ret=p["oil_ret"], names=len(w), dropped=dropped,
                           beta=p["beta"], entry_date=d, entry_i=i, exit_i=i + spec.hold, equity_basis=p["equity"], costs=0.0,
                           borrow=0.0, air_pnl=0.0, hedge_pnl=0.0, delisted=0, exit_no_open=0, tickers=",".join(str(panel.ticker.get(k, k)) for k in w.index))
                legs = {k: p["side"] * n * w[k] for k in w.index}
                legs["SPY"] = -p["side"] * p["beta"] * n
                for key, v in legs.items():
                    cash -= v
                    c = (cs if key == "SPY" else ca) * abs(v)
                    cash -= c
                    cur["costs"] += c
                    pos[key] = v
                if spec.fill == "open_next":                     # entry at the open: mark open -> close
                    for key in pos:
                        o = (panel.etf["open"]["SPY"] if key == "SPY" else panel.open[key]).iloc[i]
                        c_ = (panel.etf["close"]["SPY"] if key == "SPY" else panel.close[key]).iloc[i]
                        pnl = pos[key] * (c_ / o - 1) if np.isfinite(c_) and c_ > 0 and o > 0 else 0.0
                        pos[key] += pnl
                        cur["air_pnl" if key != "SPY" else "hedge_pnl"] += pnl
        if exit_now and cur is not None and not pos:
            trades.append(dict(cur, exit_date=d, net_pnl=cur["air_pnl"] + cur["hedge_pnl"] - cur["costs"] - cur["borrow"]))
            cur = None
        # 4: borrow for the night after this close
        if pos and i < hi:
            nights = (dates[i + 1] - d).days
            short_mv = -sum(v for v in pos.values() if v < 0)
            borrow = short_mv * br * nights / 365
            cash -= borrow
            cur["borrow"] += borrow
        equity = cash + sum(pos.values())
        # 5: new order at this close
        e = ev.iloc[i]
        if cur is None and pending is None and e.side != 0 and i + fill_lag <= hi and np.isfinite(e.z):
            w = basket(panel, i, spec)
            if len(w):
                b = hedge_beta(panel, i, w, spec)
                if np.isfinite(b):
                    pending = dict(due=i + fill_lag, date=d, side=int(e.side), z=float(e.z), oil_ret=float(e.oil_ret), w=w, beta=b, equity=equity)
        if cur is not None and cur["exit_i"] > hi:                 # cannot exit inside the run: close at the final close
            cur["exit_i"] = hi
        rows.append(dict(date=d, equity=equity, ret=equity / eq_prev - 1, in_trade=int(bool(pos)), gross=sum(abs(v) for v in pos.values()) / equity,
                         borrow=borrow, event=int(e.side != 0)))
        eq_prev = equity
    if cur is not None and pos:                                     # liquidate at the final close
        for key in list(pos):
            close_out(key, pos.pop(key), cs if key == "SPY" else ca)
        trades.append(dict(cur, exit_date=dates[hi], net_pnl=cur["air_pnl"] + cur["hedge_pnl"] - cur["costs"] - cur["borrow"]))
        rows[-1].update(equity=cash, in_trade=0, gross=0.0)
        rows[-1]["ret"] = cash / (rows[-2]["equity"] if len(rows) > 1 else spec.initial_equity) - 1
    daily = pd.DataFrame(rows).set_index("date")
    tr = pd.DataFrame(trades)
    if len(tr):
        tr["pnl_pct"] = tr.net_pnl / tr.equity_basis
    return daily, tr


def reconcile(daily, trades, spec, tol=0.01):
    if not len(daily) or not np.isfinite(daily.equity.to_numpy(float)).all():
        raise ReconciliationError("non-finite equity")
    if len(trades) and not np.isfinite(trades[["air_pnl", "hedge_pnl", "costs", "borrow", "net_pnl"]].to_numpy(float)).all():
        raise ReconciliationError("non-finite trade values")
    err = float(daily.equity.iloc[-1] - spec.initial_equity - (trades.net_pnl.sum() if len(trades) else 0.0))
    if not np.isfinite(err) or abs(err) > tol:
        raise ReconciliationError(f"trade P&L does not reconcile to equity: {err:,.4f}")
    return err
