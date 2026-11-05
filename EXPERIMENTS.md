# Experiment log (append-only)

Every run of `run_study.py` on real data adds a row. Design changes after any result is seen are added with the reason.

| date | period | variant | spec hash | headline | note |
|---|---|---|---|---|---|
| 2026-11-04 | pre-registration | all | see docs/SPEC.md | no data extracted | weight cap changed to max(25%, 1/N) before any data: a 25% cap is unattainable with three names |
| 2026-11-04 | pre-registration | all | changed (exclude field added) | universe check only: names, identifiers and row counts, no returns | excluded three non-passenger SIC 4512 stocks (Cryoport, Era/Bristow, AirNet); extraction now keeps delisting-day rows, which lack common-stock attributes; exits use CRSP's delisting flag because permno 21020 was reused (AMR, then AAL) |
