# Pre-registration: do airline stocks under-react to large oil moves?

Written 2026-11-04, before any data for this project was extracted or examined. Changing anything below changes the specification
hash in `config.py`; every change after the first evaluation is logged in `EXPERIMENTS.md` with its reason.

## Hypothesis
Jet fuel is roughly a fifth to a third of a US airline's operating costs, so a large oil move changes expected airline earnings.
If investors under-react, airline stocks keep moving in the direction implied by the oil move for several sessions after it:
after a large oil rise, airlines underperform the market; after a large oil fall, they outperform.
The null is no continuation. A reversal (the opposite sign) would also be reported as a finding, not tuned away.

## Data (CRSP via WRDS; nothing hand-picked)
- **Oil:** the United States Oil Fund (USO), which holds front-month WTI futures and trades on the same exchange clock as the
  stocks, so a close-to-close oil move and the stocks' closes are simultaneous. It carries roll costs and changed its holdings in
  2020; it is used as a signal, not traded.
- **Airlines:** every CRSP common stock (share type NS, security type EQTY, sub-type COM, US-incorporated, NYSE/AMEX/Nasdaq) with
  SIC 4512 (scheduled air transportation) **on the date in question**, so mergers, bankruptcies and new listings enter and leave
  the universe as they happened. Returns include CRSP's delisting returns.
  - *Exclusions (fixed from company names before any returns were pulled):* three SIC 4512 stocks are not scheduled passenger
    carriers and are excluded throughout: Cryoport (CYRX, permno 15506; life-science cold-chain logistics), Era Group / Bristow
    (ERA, VTOL, permno 13743; helicopter services, largely for offshore oil and gas, so its oil exposure has the opposite sign),
    and AirNet Systems (ANS, permno 83467; air cargo).
  - *Delistings:* every daily row of any stock that qualified at some point is extracted, because CRSP's delisting-day rows do not
    carry the common-stock attributes and filtering rows would drop the delisting return. Eligibility for a new basket uses the
    attributes on that day; a held stock is marked on CRSP's delisting day (flag `dlydelflg`) with that day's return, which
    includes the delisting return, and its value then moves to cash.
  - *Identifier reuse and gaps:* CRSP can resume a permno after months without rows and with no delisting flag at the gap: AMR's
    21020 stops on 2012-01-04 (NYSE delisting in bankruptcy) and resumes as American Airlines Group on 2013-12-09; Spirit's
    12796 stops on 2024-11-15 and resumes on 2025-04-29 as new equity issued in reorganization (the old shares were cancelled).
    So an exit is never inferred from later data. When a stock has no row for more than 10 sessions, its last row before the gap
    is its exit and later rows are a different security. No delisting return exists for these exits, so a position held into
    one would miss the post-exchange loss; ingest reports whether either stock was basket-eligible ($5 price, $500M cap) just
    before its gap. A gap of 10 sessions or fewer is a trading halt: no return is earned.
  - *Limitation:* regional carriers (SkyWest, Mesa, Republic, ExpressJet, Pinnacle) mostly fly under capacity-purchase contracts
    in which the major carrier pays for fuel, so their oil exposure is weaker. They stay in the universe, as SIC 4512 records
    them; excluding them on that ground would be a judgement about exposure, which the rule does not make.
- **Hedge:** SPDR S&P 500 ETF (SPY). **Risk-free and market:** Fama-French daily and monthly factors.

## Signal (decided at a close, using only data up to that close)
- Oil move z_t = USO close-to-close return on day t divided by the standard deviation of USO daily returns over the previous 60
  sessions (t-60 to t-1).
- An event occurs when |z_t| >= 2.0. Position side = -sign(USO return): short airlines after an oil rise, long after an oil fall.
- New events are ignored while a position is open or pending.

## Position
- **Basket:** eligible airlines on day t with a market cap of at least $500M and a price of at least $5 at the close of t, weighted by
  market cap at that close, each weight capped at the larger of 25% and 1/N for N names (excess redistributed proportionally;
  with three names the cap is one third). At least 3 names, otherwise no trade.
- **Hedge:** SPY in the opposite direction, sized at beta x basket notional, where beta is the OLS slope of the fixed-weight basket's
  daily return on SPY's over the 252 sessions ending at t, clipped to [0.5, 2.0].
- **Size:** basket notional = 50% of equity at the close of t; hedge notional = beta x that.
- **Execution:** fill at the open of t+1 (primary); exit at the open of the session H sessions after the entry fill; H = 5 (primary).
- **Frictions (assumptions):** 10 bps per side on airline notional, 2 bps per side on SPY; borrow 50 bps a year on short market
  value, per night; no interest on cash (financing is a separate analysis, as in the V/MA study).
- No stop-loss, no profit target, no other filters.

## Periods and evaluation discipline
- Development 2007-01-01 to 2016-12-31; validation 2017-01-01 to 2021-12-31; holdout 2022-01-01 to 2025-12-31.
- Each period is an independent $1M run. Development may be examined freely for implementation checks; validation is run once
  per declared variant; the holdout once, primary specification only, guarded by the specification hash and `evaluations.json`.
- **Declared variants (all reported, none selected):** holding H = 1 and H = 10 sessions; fill at the next close; equal weights.

## Primary outcome and tests
- Net mean return per trade (as a share of equity at entry) and the total-equity Sharpe of daily returns, per period.
- Trade-level t-statistic with a block bootstrap interval, and the number of events (expected roughly 10 a year).
- **Pre-stated diagnostics:** the same-day reaction of airlines to oil moves (the economic premise: it should be negative);
  results split by oil-rise and oil-fall events; results excluding 2008-09 and 2020 (crisis concentration); market beta of the strategy.

## What would count as support
A positive mean in validation and holdout with intervals excluding zero after costs, consistent signs for rise and fall events,
and a result not explained by one crisis. Anything less is reported as inconclusive. No parameter is changed in response to
validation or holdout results; ideas they suggest are logged as new hypotheses for data not yet examined.
