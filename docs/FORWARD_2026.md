# Forward test pre-registration: 2026 onward

Written 2026-11-11, before any 2026 data (prices, universe membership, or factors) has been pulled from any source.
This is a separate pre-registration from `docs/SPEC.md`, not an extension of the holdout period, for two reasons:
development/validation/holdout (2007-2025) all ran on CRSP via WRDS, and WRDS/CRSP in this environment's subscription
stops at 2025-12-31 (found while building an unrelated DCF's beta cross-check and already visible as a stated limitation
in `vma-pairs/docs/RESULTS.md`); and the holdout period has already been evaluated once, under this project's own
discipline (`evaluations.json`), so 2026+ cannot be folded into it without re-using a consumed evaluation. This period's
results are **not pooled with development/validation/holdout** in any summary statistic -- different data source,
different universe-construction method, reported on their own.

## Disclosure (what is already known when this is written)
Both I and the person running this project have ordinary, general awareness of the broad 2026 path of oil prices from
financial news encountered elsewhere, independent of this project -- that kind of awareness cannot be fully un-known,
and pretending otherwise would be less honest than naming it. Neither of us has examined airline stock returns, USO's
day-by-day path, the same-day reaction diagnostic, or any trade- or event-level data for 2026 -- nothing in this
registration (the rule, the two hypotheses, the universe procedure, the timing rule) was shaped by looking at the
thing being tested. This is disclosed rather than ignored, the same practice this project already follows for every
other judgment call (`docs/SPEC.md`, `EXPERIMENTS.md`).

## Why not just re-run the primary spec unchanged
The rule, signal, position and cost assumptions in `docs/SPEC.md` / `config.py` carry over unchanged -- no retuning.
What cannot carry over unchanged is the data pipeline: CRSP is unavailable past 2025-12-31, and CRSP's point-in-time
SIC-4512 classification (the thing that lets mergers, bankruptcies and new listings enter and leave the universe as
they happened) has no Yahoo Finance equivalent. Substituting a hand-picked ticker list from memory would both violate
this project's "nothing hand-picked" data discipline (`docs/SPEC.md`, Data section) and risk being stale -- this
project has already hit identifier-reuse and delisting surprises (AMR/AAL, Spirit) that a memory-based list would
likely miss. So the universe step below is a **procedure to run and freeze**, not a list written down now.

## Data source (declared before any pull)
- **Airlines, USO, SPY -- prices (open and close):** Yahoo Finance via `yfinance`, the same library already used in
  `payments-earnings-event-study` and `vma-pairs`. **Yahoo Finance is not a licensed, institutional data source** --
  unlike CRSP, which this project uses under a WRDS academic license (see the data note at the bottom of
  `README.md`), Yahoo's data comes with no license agreement governing its accuracy, and its prices can be revised
  retroactively. Its adjusted-close methodology (how splits and dividends are folded into a single backward-adjusted
  price series) is also not the same convention CRSP's own return calculation uses (raw prices plus explicit
  distribution events) -- so a return computed from Yahoo's adjusted closes is not a strict apples-to-apples match to
  a CRSP-computed return, on top of the universe-construction difference already noted. Both points are additional,
  separate reasons this period is not pooled with the CRSP-era ones, and are repeated under Limitations below.
- **Market and risk-free factors:** first check, as its own logged step before any returns are pulled, whether WRDS's
  `ff.factors_daily` / `ff.factors_monthly` (a different table, and a different update cadence, than the CRSP CIZ
  tables that cap at 2025-12-31) already covers 2026. If it does, use it unchanged -- same source as every prior
  period. If it does not, substitute: SPY's own daily return (already pulled as the hedge instrument) as the market
  factor, and a FRED Treasury-bill series (e.g. `DTB3`) as the risk-free rate -- consistent with how
  `financial-models`' WACC sourced its risk-free rate from FRED and `payments-earnings-event-study` sourced its
  risk-free rate from a public series rather than a proprietary one, both on 2026-11-11. This fallback choice is
  fixed now, not decided after seeing which table is available.
- **Universe (airlines in scope):** not a hand-picked list. Procedure, to be executed and frozen as its own logged
  step, with no returns pulled until the resulting list is written down:
  1. Query SEC EDGAR's company search for SIC code 4512 ("Air Transportation, Scheduled"), as of a stated freeze
     date, to get every registrant with that SIC code.
  2. Keep registrants with a US common-equity listing on NYSE, NYSE American or Nasdaq (matching the exchange
     restriction already in `docs/SPEC.md`'s CRSP universe definition) and exclude anything without a currently
     trading ticker (shells, already-delisted registrants with no successor).
  3. Apply the same exclusion standard already used for the CRSP universe -- a company correctly coded SIC 4512 but
     whose business is not scheduled passenger service is excluded, with the reason stated at exclusion time, before
     any price or return is examined. (The three CRSP-era exclusions -- Cryoport, Era/Bristow, AirNet -- are specific
     CRSP permnos from the 2007-2025 universe and do not automatically carry over; EDGAR's own 2026 SIC-4512 list is
     checked fresh against the same standard.)
  4. The result is a **static** list for the whole forward period -- unlike CRSP's point-in-time universe, it is not
     re-derived day by day. This is a real, named downgrade from the primary methodology (see Limitations).
  This procedure is written down now; running it (step 1) is the first action that needs a go-ahead, separate from
  pulling any price history.

## Rule, position and costs
Unchanged from `docs/SPEC.md` / `config.py`'s primary specification: z-threshold 2.0 on USO's 60-session return
volatility, market-cap-weighted basket (cap 25% or 1/N) hedged with SPY at clipped trailing beta, next-open fill,
5-session hold, 10bps/2bps costs, 50bps borrow. No parameter changes -- the point of this period is to see whether the
same, already-frozen rule still does anything, not to find a better one on new data.

## Hypotheses (both fixed now, before any 2026 data)

**H_main (replication).** The same continuation hypothesis as `docs/SPEC.md`: after a large oil move, airlines keep
moving in the implied direction for 5 sessions, net of costs and the market. Reported on its own, not pooled with the
CRSP-era periods, because the data source and universe-construction method differ.

**H_conditioned (from `EXPERIMENTS.md`, 2026-11-04 entry: "continuation exists only when airlines are trading off oil
... testable only on data not yet examined (2026 onward), with the condition fixed in advance").** That entry is a
hypothesis suggested by the validation-period result, not evidence -- fixing its test now, before 2026 data is seen,
is what makes it a real test rather than another after-the-fact story:
- **The condition:** compute the same-day reaction already defined as a pre-stated diagnostic in `docs/SPEC.md`
  ("the same-day reaction of airlines to oil moves... it should be negative") over the 2026 forward window: the OLS
  slope of the basket's same-day return on USO's same-day return, on event days.
- **The prediction:** if that slope is negative (airlines are once again trading off oil same-day, as in development
  and the holdout, not as in validation where this went away), H_conditioned predicts continuation reappears with a
  positive mean net return, matching development's and the holdout's sign. If the slope is zero or positive (as in
  validation), H_conditioned predicts no continuation -- the same null as validation, for the same stated reason.
- This is checked once, against whatever the slope's sign turns out to be -- not used to pick which of two stories to
  tell afterward.

## Power (declared before any 2026 data)
Prior periods' event rates, from the pre-stated diagnostics already recorded in `docs/RESULTS.md`: development 9.9
events/year (99 trades over 10 years), validation 10.4/year (52 over 5), holdout 8.0/year (32 over 4). One calendar
year of 2026 therefore gives roughly **8 to 10 trades** for H_main -- an order of magnitude fewer than development's
99 or even the holdout's 32, the two periods whose intervals actually excluded zero. H_conditioned's condition (the
same-day reaction slope's sign) is estimated from that same one-year window rather than development's 10 years,
validation's 5, or the holdout's 4, so it is a noisier estimate of the same quantity that took a full period to
pin down in every prior case; H_conditioned's prediction rests on fewer effective data points than even H_main's
already-thin 8-10 trades.

**Stated in advance, regardless of what the point estimate looks like:** 2026's result for both H_main and
H_conditioned will be reported descriptively only -- mean, t-statistic, 95% bootstrap interval, the same format as
`docs/RESULTS.md`'s table -- and will **not** be called "supported" or "refuted" on its own. This project's own
evaluation standard already required a positive, interval-excluding-zero result in both validation (5 years) and the
holdout (4 years) before calling anything supported (`docs/SPEC.md`, "What would count as support"); one year of
8-10 trades cannot clear or fail that bar, only be reported against it.

**This registration covers calendar year 2026 only. It does not automatically extend through 2027.** If 2026's
result -- whatever it turns out to be -- suggests the forward window should be extended, that is a new, separate
decision, to be made and logged in `EXPERIMENTS.md` *before* any 2027 data is examined, not an automatic
continuation of this registration. The point is to stop an unclear or unfavorable 2026 result from quietly turning
into "add another year and see."

## Evaluation discipline
- **Timing, fixed now to prevent peeking:** evaluated once, the first time this period is run, no earlier than
  2027-01-01 (so every event's 5-session hold has had the chance to close) and using whatever 2026 data exists at
  that time -- not re-run partway through the year to check how it looks, and not delayed further if an early look
  (there will not be one) seems unfavorable.
- Three separate, logged steps before any strategy result exists, mirroring how `docs/SPEC.md`'s own universe and
  data-quality checks were logged before the first real run: (1) freeze the EDGAR-based universe, (2) pull and
  ingest 2026 prices/factors, with a data-quality report before any return is examined, (3) run H_main and
  H_conditioned together, once. Each step needs a go-ahead; none has happened yet.
- Logged in `EXPERIMENTS.md` and `evaluations.json` exactly like every other evaluation in this project. No parameter
  is changed in response to this period's result, on either hypothesis.

## What would count as support
**H_main:** a positive mean net return with an interval excluding zero, consistent in sign with development and the
holdout. **H_conditioned:** the same-day slope's sign correctly predicting whether continuation appears at all.
Anything else is reported as inconclusive, same standard as `docs/SPEC.md` -- but see "Power" above: with only 8-10
trades expected, this is the standard against which the one-year result is read, not a verdict it is expected to
settle. A result that happens to clear this bar on 8-10 trades is reported as such, with the interval shown, and
described as thin evidence, not as confirmation.

## Limitations of this design (declared before results, not after)
- The universe is static for the whole period, not point-in-time like CRSP's -- a 2026 merger or bankruptcy would
  not remove or add a name mid-period the way CRSP's SIC-4512-on-the-date rule does for 2007-2025. This is a real
  reduction in data quality from the primary periods, not a stylistic difference.
- Yahoo Finance is an unlicensed source (see "Data source" above) whose prices can be revised and which carries no
  delisting-return concept; a name that delists mid-period would need a manual check against a primary source (e.g.
  an 8-K) rather than relying on the price feed to reflect it. Its adjusted-price convention also differs from
  CRSP's, so returns from the two sources are not a strict like-for-like comparison even where the same economic
  event is involved.
- If the market/risk-free fallback (SPY return, FRED T-bill) is used instead of the Fama-French factors every prior
  period used, the market-beta diagnostic in `docs/SPEC.md` is not computed on an identical factor definition to
  2007-2025, and that difference is reported alongside any beta number for this period.
- Because of the above, this period's result is informative on its own terms but is not strong evidence either way
  about the primary, CRSP-based specification -- it answers "does this still look true on 2026 data," not "is the
  2007-2025 result robust," which are different questions.
