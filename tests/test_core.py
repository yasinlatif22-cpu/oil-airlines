from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from config import DEFAULT
from data_io import build_panel, split_at_gaps, synthetic
from engine import ReconciliationError, reconcile, run_engine
from signals import basket, capped_weights, oil_events
from tests.helpers import hand_market

FREE = replace(DEFAULT, cost_airline_bps=0.0, cost_spy_bps=0.0, borrow_bps=0.0, beta_min=1.0, beta_max=1.0)


def test_hand_calculated_short_trade():
    p, idx = hand_market()
    daily, tr = run_engine(p, FREE, idx[260], idx[-1])
    assert len(tr) == 1
    t = tr.iloc[0]
    assert t.side == -1 and t.signal_date == idx[300] and t.entry_date == idx[301] and t.exit_date == idx[306]
    # four names at 25% of a $500k short: -125k each. Open 50 -> close 49 (+2.5k each); close 49 -> exit open 48 (+2.5k each)
    assert t.air_pnl == pytest.approx(4 * 5000.0)
    assert t.hedge_pnl == pytest.approx(0.0) and t.net_pnl == pytest.approx(20000.0)
    assert reconcile(daily, tr, FREE) == pytest.approx(0, abs=1e-6)


def test_costs_and_borrow_by_hand():
    p, idx = hand_market()
    spec = replace(FREE, cost_airline_bps=10.0, cost_spy_bps=2.0, borrow_bps=50.0)
    daily, tr = run_engine(p, spec, idx[260], idx[-1])
    t = tr.iloc[0]
    entry = 0.001 * 500_000 + 0.0002 * 500_000
    exit_ = 0.001 * 4 * 125_000 * 0.98 * (48 / 49) + 0.0002 * 500_000
    assert t.costs == pytest.approx(entry + exit_)
    nights = sum((idx[k + 1] - idx[k]).days for k in range(301, 306))          # closes s+1 .. s+5 are held
    assert t.borrow == pytest.approx(4 * 125_000 * 0.98 * 0.005 * nights / 365)
    assert reconcile(daily, tr, spec) == pytest.approx(0, abs=1e-6)


def test_signal_uses_past_volatility_only():
    p, idx = hand_market()
    ev = oil_events(p, DEFAULT)
    q = build_panel(*_perturbed_future(p, 301))
    ev2 = oil_events(q, DEFAULT)
    pd.testing.assert_frame_equal(ev.iloc[:301], ev2.iloc[:301])
    assert ev.side.iloc[300] == -1 and (ev.side.iloc[200:300] == 0).all()


def _perturbed_future(p, cut, seed=0):
    rng = np.random.default_rng(seed)
    stocks, etf = [], []
    for k in p.close.columns:
        f = pd.DataFrame({"date": p.dates, "permno": k, "ticker": p.ticker[k], "open": p.open[k], "close": p.close[k], "ret": p.ret[k],
                          "div": p.div[k], "mktcap": p.mktcap[k]})
        m = rng.uniform(0.5, 2.0, len(f) - cut)
        for c in ("open", "close", "mktcap"):
            f.loc[f.index[cut:], c] = f[c].iloc[cut:].to_numpy() * m
        f.loc[f.index[cut:], "ret"] = rng.normal(0, 0.05, len(f) - cut)
        stocks.append(f)
    for tk in ("USO", "SPY"):
        f = pd.DataFrame({"date": p.dates, "ticker": tk, **{c: p.etf[c][tk] for c in ("open", "close", "ret", "div")}})
        f.loc[f.index[cut:], "ret"] = rng.normal(0, 0.05, len(f) - cut)
        etf.append(f)
    return pd.concat(stocks, ignore_index=True), pd.concat(etf, ignore_index=True)


def test_future_data_cannot_change_the_past_ledger():
    s, e = synthetic(seed=3, continuation=0.5)
    p = build_panel(s, e)
    daily, tr = run_engine(p, DEFAULT, p.dates[300], p.dates[-1])
    it = daily.in_trade.to_numpy()
    held = np.flatnonzero((it == 1) & (np.r_[0, it[:-1]] == 1))   # marked from a held close: a peek at the next day would show
    for k, j in enumerate(held[[0, len(held) // 2, -1]]):
        cut = 300 + j + 1                                    # first perturbed session follows a close at which a position is held
        if cut >= len(p.dates) - 2:
            continue
        q = build_panel(*_perturbed_future(p, cut, seed=k))
        d2, _ = run_engine(q, DEFAULT, p.dates[300], p.dates[-1])
        pd.testing.assert_frame_equal(daily.iloc[: j + 1], d2.iloc[: j + 1])


def test_basket_is_point_in_time_and_capped():
    p, idx = hand_market(caps=(4e8, 1e9, 2e9, 3e9, 4e9))       # the first name is below $500M and is excluded
    w = basket(p, 300, DEFAULT)
    assert 1 not in w.index and w.max() <= 0.25 + 1e-12 and w.sum() == pytest.approx(1.0)
    w3 = capped_weights(pd.Series([1.0, 2.0, 3.0]), 0.25)       # three names: the cap becomes one third
    assert np.allclose(w3, 1 / 3)
    p2, _ = hand_market(caps=(1e9, 1e9))
    assert basket(p2, 300, DEFAULT).empty                       # fewer than three names: no trade


def test_a_name_leaving_crsp_mid_trade_goes_to_cash_with_its_delisting_return():
    s0, e0 = synthetic(seed=5, continuation=0.0)
    p0 = build_panel(s0, e0)
    _, t0 = run_engine(p0, DEFAULT, p0.dates[300], p0.dates[-1])
    t = next(r for r in t0.itertuples() if "AIR0" in r.tickers.split(","))      # a trade holding the first airline
    day = p0.dates.get_loc(t.entry_date) + 2                                     # it leaves CRSP two sessions into the trade
    s, e = synthetic(seed=5, continuation=0.0, delist=(0, day))
    p = build_panel(s, e)
    daily, tr = run_engine(p, DEFAULT, p.dates[300], p.dates[-1])
    reconcile(daily, tr, DEFAULT)
    hit = tr[tr.entry_date == t.entry_date].iloc[0]
    assert hit.delisted == 1                                                     # recorded, and its value moved to cash
    assert hit.air_pnl != pytest.approx(t.air_pnl)                               # the -50% delisting return was booked


def test_reconcile_rejects_non_finite_values():
    p, idx = hand_market()
    daily, tr = run_engine(p, FREE, idx[260], idx[-1])
    bad = daily.copy(); bad.iloc[-1, bad.columns.get_loc("equity")] = np.nan
    with pytest.raises(ReconciliationError):
        reconcile(bad, tr, FREE)


def test_planted_under_reaction_is_found_and_null_is_not():
    # predetermined seeds; a loose check that the engine can see a planted effect, not a significance requirement
    def mean_trade(cont, seed):
        s, e = synthetic(seed=seed, n=2000, continuation=cont)
        p = build_panel(s, e)
        _, tr = run_engine(p, DEFAULT, p.dates[300], p.dates[-1])
        return tr.pnl_pct.mean()
    planted = [mean_trade(1.0, k) for k in (11, 12, 13)]
    null = [mean_trade(0.0, k) for k in (11, 12, 13)]
    assert all(x > 0 for x in planted) and np.mean(planted) > np.mean(null) + 0.004


def test_non_members_and_excluded_names_never_enter_the_basket():
    p, idx = hand_market(caps=(1e9, 2e9, 3e9, 4e9, 5e9))
    p.member.loc[idx[300], 5] = 0                              # not recorded as an eligible common stock that day
    assert 5 not in basket(p, 300, DEFAULT).index and 5 in basket(p, 299, DEFAULT).index
    from ingest import membership
    raw = pd.DataFrame({"permno": [15506, 21020, 21020, 21020], "siccd": [4512, 4512, 4512, 9999],
                        "sharetype": ["NS", "NS", None, "NS"], "securitytype": ["EQTY", "EQTY", None, "EQTY"],
                        "securitysubtype": ["COM", "COM", None, "COM"], "usincflg": ["Y", "Y", None, "Y"],
                        "primaryexch": ["Q", "N", None, "N"], "dlydelflg": ["N", "N", "Y", "N"]})
    member, delist = membership(raw, DEFAULT)
    assert member.tolist() == [0, 1, 0, 0]          # excluded by name; eligible; delisting row; another SIC that day
    assert delist.tolist() == [0, 0, 1, 0]          # the delisting row is kept and flagged, even without the attributes


def test_a_reused_identifier_does_not_keep_a_delisted_position_open():
    s0, e0 = synthetic(seed=5, continuation=0.0)
    p0 = build_panel(s0, e0)
    _, t0 = run_engine(p0, DEFAULT, p0.dates[300], p0.dates[-1])
    t = next(r for r in t0.itertuples() if "AIR0" in r.tickers.split(","))
    day = p0.dates.get_loc(t.entry_date) + 2
    gone, _ = synthetic(seed=5, continuation=0.0, delist=(0, day))
    back, _ = synthetic(seed=5, continuation=0.0, delist=(0, day, day + 60))     # the permno reappears 60 sessions later
    assert (back.permno == 10000).sum() > (gone.permno == 10000).sum()
    res = []
    for s in (gone, back):
        p = build_panel(s, e0)
        daily, tr = run_engine(p, DEFAULT, p.dates[300], p.dates[day + 30])
        reconcile(daily, tr, DEFAULT)
        res.append(tr[tr.entry_date == t.entry_date].iloc[0])
    assert res[0].delisted == res[1].delisted == 1                               # the flag, not missing data, closes it
    assert res[0].air_pnl == pytest.approx(res[1].air_pnl)                       # later data cannot reopen the position


def test_a_long_gap_without_a_delisting_flag_is_an_exit_and_a_new_security():
    s0, e0 = synthetic(seed=5, continuation=0.0)
    p0 = build_panel(s0, e0)
    _, t0 = run_engine(p0, DEFAULT, p0.dates[300], p0.dates[-1])
    t = next(r for r in t0.itertuples() if "AIR0" in r.tickers.split(","))
    day = p0.dates.get_loc(t.entry_date) + 2
    back, _ = synthetic(seed=5, continuation=0.0, delist=(0, day, day + 60))
    back["delist"] = 0                                          # as with AMR and Spirit: CRSP sets no flag at the gap
    seg = split_at_gaps(back, p0.dates, DEFAULT.gap_sessions)
    a0 = seg[seg.crsp_permno == 10000]
    assert a0.permno.nunique() == 2 and a0.gap_exit.sum() == 1 and a0[a0.gap_exit == 1].date.iloc[0] == p0.dates[day]
    assert split_at_gaps(s0, p0.dates, DEFAULT.gap_sessions).gap_exit.sum() == 0      # no gaps, nothing changes
    p = build_panel(seg, e0)
    daily, tr = run_engine(p, DEFAULT, p.dates[300], p.dates[day + 90])
    reconcile(daily, tr, DEFAULT)
    hit = tr[tr.entry_date == t.entry_date].iloc[0]
    assert hit.delisted == 1 and hit.exit_date == p.dates[day + 3]          # the name left at the gap; the trade ended on schedule


def test_an_exit_never_uses_a_zero_open_price():
    p, idx = hand_market()
    _, t0 = run_engine(p, FREE, idx[290], idx[-1])
    p.open.loc[idx[306], 1] = 0.0                               # CRSP writes price 0 on delisting rows
    _, t1 = run_engine(p, FREE, idx[290], idx[-1])
    assert t1.net_pnl.iloc[0] == pytest.approx(t0.net_pnl.iloc[0])          # here the day's return gives the same exit value


def test_placeholder_rows_are_dropped_so_the_gap_is_seen():
    from ingest import drop_placeholders
    s0, e0 = synthetic(seed=5, continuation=0.0)
    p0 = build_panel(s0, e0)
    s = s0.copy()
    gap = (s.permno == 10000) & s.index.isin(s[s.permno == 10000].index[400:460])
    s.loc[gap, ["open", "close", "ret", "mktcap"]] = float("nan")          # off-exchange: rows with nothing in them
    kept, empty = drop_placeholders(s)
    assert len(empty) == 60 and split_at_gaps(kept, p0.dates, DEFAULT.gap_sessions).gap_exit.sum() == 1
    assert split_at_gaps(s, p0.dates, DEFAULT.gap_sessions).gap_exit.sum() == 0          # without dropping, the gap is hidden

