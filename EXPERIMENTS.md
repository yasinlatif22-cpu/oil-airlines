# Experiment log (append-only)

Every run of `run_study.py` on real data adds a row. Design changes after any result is seen are added with the reason.

| date | period | variant | spec hash | headline | note |
|---|---|---|---|---|---|
| 2026-11-04 | pre-registration | all | see docs/SPEC.md | no data extracted | weight cap changed to max(25%, 1/N) before any data: a 25% cap is unattainable with three names |
| 2026-11-04 | pre-registration | all | changed (exclude field added) | universe check only: names, identifiers and row counts, no returns | excluded three non-passenger SIC 4512 stocks (Cryoport, Era/Bristow, AirNet); extraction now keeps delisting-day rows, which lack common-stock attributes; exits use CRSP's delisting flag because permno 21020 was reused (AMR, then AAL) |
| 2026-11-04 | pre-registration | all | changed (gap_sessions added) | universe check only: delisting rows and identifier dates, no returns analysed | AMR (21020) and Spirit (12796) leave the exchanges with no delisting flag and later resume under the same permno; a gap of more than 10 sessions is now an exit and a new security. Exit fills never use CRSP's zero price on delisting rows |
| 2026-11-04 | data quality | all | unchanged (7b38eeb2262b) | ingest report only: universe, exits, placeholder rows, missing opens, large daily moves; no strategy run | CRSP keeps empty off-exchange rows for AMR and Spirit; they are dropped so the gap rule applies. Neither stock was basket-eligible before its gap. Exits without an opening price are counted per trade |
