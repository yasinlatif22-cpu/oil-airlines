# Results

**Verdict under the pre-registered criteria: inconclusive.** [`docs/SPEC.md`](SPEC.md) required a positive mean in both
validation and holdout, with intervals excluding zero after costs, consistent signs for oil-rise and oil-fall events, and no
dependence on one crisis. The holdout meets those conditions; validation does not. Its mean is negative, and its long and
short sides point in opposite directions. Nothing was changed in response to either result.

All figures are net of costs and borrow, per trade as a share of equity at entry, specification hash `7b38eeb2262b`.
The t-statistics are plain t on non-overlapping trades. The intervals are 95% bootstrap intervals.

## Primary specification

| period | trades | mean / trade | t | 95% interval | Sharpe | max drawdown |
|---|---:|---:|---:|---|---:|---:|
| development 2007-16 | 99 | +0.22% | +0.80 | [-0.32%, +0.77%] | 0.27 | -17.4% |
| validation 2017-21 | 52 | -0.40% | -1.66 | [-0.90%, +0.05%] | -0.42 | -24.4% |
| holdout 2022-25 | 32 | +0.80% | +2.59 | [+0.21%, +1.40%] | 0.98 | -5.4% |
| all pooled (context, not a test) | 183 | +0.15% | +0.83 | [-0.20%, +0.50%] | | |

## Pre-stated diagnostics (`python diagnostics.py`)

| | development | validation | holdout |
|---|---:|---:|---:|
| same-day airline response to USO, controlling for SPY (premise: negative) | -0.40 (t -11.8) | **+0.03 (t +0.5)** | -0.13 (t -4.0) |
| after oil falls (long airlines) | +0.47%, n=53 | -0.71%, n=35 | +0.55%, n=18 |
| after oil rises (short airlines) | -0.06%, n=46 | +0.25%, n=17 | +1.11%, n=14 |
| excluding entries in 2008, 2009, 2020 | +0.02%, n=82 | -0.12%, n=40 | +0.80%, n=32 |
| strategy beta to SPY | -0.01 | +0.04 | +0.02 |
| events per year | 9.9 | 10.4 | 8.0 |

The hedge works: the strategy's market beta is near zero in every period.

- **Development:** the premise holds strongly: airlines fall about 0.4% for each 1% rise in USO on the same day. Even so,
  there is no follow-through. The positive mean comes from 2008-09; without those years it is +0.02%.
- **Validation:** the premise fails. Over 2017-21, airline stocks did not move against oil on the same day at all. In 2020
  both crashed together, and in April 2020 USO changed its holdings away from the front-month contract. With no same-day
  link, the rule has nothing to trade on.
- **Holdout:** the premise holds again, and so does the continuation, on both sides. But this is 32 trades in one period.

## Declared variants, validation period (all reported, none selected)

| variant | trades | mean / trade | t | 95% interval |
|---|---:|---:|---:|---|
| primary (5-session hold, next-open fill, capped value weights) | 52 | -0.40% | -1.66 | [-0.90%, +0.05%] |
| 1-session hold | 74 | -0.06% | -0.45 | [-0.32%, +0.19%] |
| 10-session hold | 40 | -0.57% | -1.83 | [-1.20%, +0.03%] |
| fill at the next close | 52 | -0.31% | -1.24 | [-0.77%, +0.19%] |
| equal weights | 52 | -0.36% | -1.32 | [-0.91%, +0.16%] |

## What this does and does not show
- After a large oil move, there is no reliable continuation in airline stocks over the following week across 2007-2025.
  One of three periods is positive and significant, one is negative, and pooled the effect is not distinguishable from zero.
- The results suggest the continuation exists only when airlines are actually trading off oil. That idea came from looking
  at these results, so it is **not** a finding. It is logged as a new hypothesis in `EXPERIMENTS.md`, to be tested only on
  data not yet examined (2026 onward).
- **Limitations:**
  - USO is an imperfect oil proxy: it carries roll costs, and its holdings changed in 2020.
  - The universe is small (10 to 19 names a year), and regional carriers with fuel passed through to their partners remain
    in it.
  - Bid-ask costs for the smaller names were likely above 10 bps in 2008-09.
