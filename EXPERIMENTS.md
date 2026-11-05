# Experiment log (append-only)

Every run of `run_study.py` on real data adds a row. Design changes after any result is seen are added with the reason.

| date | period | variant | spec hash | headline | note |
|---|---|---|---|---|---|
| 2026-11-04 | pre-registration | all | see docs/SPEC.md | no data extracted | weight cap changed to max(25%, 1/N) before any data: a 25% cap is unattainable with three names |
| 2026-11-04 | pre-registration | all | changed (exclude field added) | universe check only: names, identifiers and row counts, no returns | excluded three non-passenger SIC 4512 stocks (Cryoport, Era/Bristow, AirNet); extraction now keeps delisting-day rows, which lack common-stock attributes; exits use CRSP's delisting flag because permno 21020 was reused (AMR, then AAL) |
| 2026-11-04 | pre-registration | all | changed (gap_sessions added) | universe check only: delisting rows and identifier dates, no returns analysed | AMR (21020) and Spirit (12796) leave the exchanges with no delisting flag and later resume under the same permno; a gap of more than 10 sessions is now an exit and a new security. Exit fills never use CRSP's zero price on delisting rows |
| 2026-11-04 | data quality | all | unchanged (7b38eeb2262b) | ingest report only: universe, exits, placeholder rows, missing opens, large daily moves; no strategy run | CRSP keeps empty off-exchange rows for AMR and Spirit; they are dropped so the gap rule applies. Neither stock was basket-eligible before its gap. Exits without an opening price are counted per trade |
| 2026-11-04 | dev | primary | 7b38eeb2262b | 99 trades, mean 0.223%/trade, Sharpe 0.27 | code 54ec3ed |
| 2026-11-04 | val | primary | 7b38eeb2262b | 52 trades, mean -0.397%/trade, Sharpe -0.42 | code 620047e+uncommitted |
| 2026-11-04 | holdout | primary | 7b38eeb2262b | 32 trades, mean 0.797%/trade, Sharpe 0.98 | code 620047e+uncommitted |
| 2026-11-04 | note | - | 7b38eeb2262b | - | the '+uncommitted' stamps on the val and holdout rows (and in evaluations.json) refer only to the run logs themselves (EXPERIMENTS.md, evaluations.json); no code differed from 620047e. The stamp now ignores those two files |
| 2026-11-05 | val | hold1 | e2c84e88e27f | 74 trades, mean -0.059%/trade, Sharpe -0.17 | code 5489d8d |
| 2026-11-05 | val | hold10 | 42b6e5497453 | 40 trades, mean -0.574%/trade, Sharpe -0.39 | code 5489d8d |
| 2026-11-05 | val | close_fill | 352897927753 | 52 trades, mean -0.307%/trade, Sharpe -0.32 | code 5489d8d |
| 2026-11-05 | val | equal_weight | e8356a21270e | 52 trades, mean -0.360%/trade, Sharpe -0.35 | code 5489d8d |
| 2026-11-04 | new hypothesis (not tested) | - | - | - | suggested by the results, so not evidence: continuation exists only when airlines are trading off oil (a negative trailing same-day response to USO). Testable only on data not yet examined (2026 onward), with the condition fixed in advance |
