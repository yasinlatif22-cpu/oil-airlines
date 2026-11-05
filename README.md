# Oil Shocks and Airline Stocks: Do Airlines Under-react?

**Question.** After a large one-day move in oil, do US airline stocks keep drifting in the direction the move implies for their
fuel costs, net of trading costs and of the market?

**Status: pre-registered, not yet run on real data.** The rule, the universe, the periods and the tests were fixed in
[`docs/SPEC.md`](docs/SPEC.md) before any data for this project was extracted. No result exists yet.

## The rule in one paragraph
At each close, the oil move is the day's return on the United States Oil Fund (USO) divided by its standard deviation over the
previous 60 sessions. When that z-score is at least 2 in absolute value, the rule takes a position at the next open: short a
market-cap-weighted basket of US airlines after an oil rise, long after an oil fall, hedged with SPY at the basket's trailing
252-session beta. The position is held for 5 sessions. The airline universe is every CRSP common stock classified as scheduled
air transportation (SIC 4512) on that date, so mergers, bankruptcies and new listings enter and leave as they happened.
Costs: 10 bps per side on airlines, 2 bps on SPY, 50 bps a year to borrow shorts.

## Evaluation discipline
Development 2007-2016, validation 2017-2021, holdout 2022-2025, each an independent $1M run. Validation runs once per declared
variant; the holdout once, primary specification only. `evaluations.json` records every completed evaluation and `run_study.py`
refuses to treat any of them as fresh. Every run is logged in `EXPERIMENTS.md`.

## Reproduce
Tested with Python 3.10.
```bash
pip install -r requirements.txt
python -m pytest                              # tests on synthetic data; no credentials or licensed data needed
python run_study.py --period synthetic        # engine demo on simulated data (not evidence)
```
With a WRDS account that includes CRSP and Fama-French (licensed data stays out of Git):
```bash
pip install -r requirements-wrds.txt
python extract_wrds.py --check                # universe by year, USO/SPY identifiers, delisting flags; saves no prices
python extract_wrds.py                        # data/raw/ (git-ignored)
python ingest.py                              # data/processed/ and a data-quality report
python run_study.py --period dev              # development
```

## Layout
`config.py` frozen specification and hash; `signals.py` oil events, basket and hedge ratio; `engine.py` dollar ledger with
next-open fills, costs, borrow, distributions and delisting; `metrics.py`; `run_study.py` evaluations; `extract_wrds.py`,
`ingest.py`, `data_io.py` data; `tests/`; `docs/`.

Data note: CRSP and Fama-French data are licensed through WRDS; this repository contains no such data. Wharton Research Data
Services (WRDS) was used in preparing this study. This service and the data available thereon constitute valuable intellectual
property and trade secrets of WRDS and/or its third-party suppliers.
