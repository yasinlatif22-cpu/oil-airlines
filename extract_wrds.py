"""Pull the licensed data from WRDS on your own machine. Credentials are entered interactively and never stored by this code.

  python extract_wrds.py --check     # coverage, the airline universe by year, USO/SPY identifiers, delisting flags; no prices saved
  python extract_wrds.py             # writes data/raw/*.csv and data/raw/extraction_log.json (git-ignored; do not publish)

Universe: every CRSP CIZ daily row (crsp.dsf_v2) of any stock recorded with SIC 4512 and common-stock attributes at some point in
2005-06 to 2025-12. All rows are pulled, including delisting days (which lack those attributes, so filtering rows would drop the
delisting return); ingest.py marks which rows are universe members, so membership stays point-in-time. USO and SPY are found by ticker and issuer name and pulled without the common-stock filter."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import wrds

START, END = "2005-06-01", "2025-12-31"
COMMON = "sharetype = 'NS' and securitytype = 'EQTY' and securitysubtype = 'COM' and usincflg = 'Y' and primaryexch in ('N', 'A', 'Q')"
FIELDS = ("permno, ticker, siccd, sharetype, securitytype, securitysubtype, usincflg, primaryexch, dlycaldt, dlyprc, dlyopen, dlyclose, "
          "dlyret, dlyretx, dlycumfacpr, dlycap, shrout, dlydelflg")
# every row (including delisting days, which lack the common-stock attributes) of any stock that qualified at some point
QUALIFIED = f"select distinct permno from crsp.dsf_v2 where siccd = 4512 and {COMMON} and dlycaldt between '{START}' and '{END}'"
RAW = Path("data/raw")


def etf_permnos(db):
    q = ("select distinct permno, ticker, issuernm, securitybegdt, securityenddt from crsp.stksecurityinfohist "
         "where ticker in ('USO', 'SPY')")
    df = db.raw_sql(q)
    print(df.to_string(index=False))
    pick = {}
    squash = df.issuernm.fillna("").str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)   # CRSP writes "SPDR S & P 500 E T F TRUST"
    for tk, name in (("USO", "UNITEDSTATESOIL"), ("SPY", "SPDRSP500")):
        c = df[(df.ticker == tk) & squash.str.contains(name)].permno.unique()
        if len(c) != 1:
            raise SystemExit(f"{tk}: expected one permno for issuer '{name}', found {list(c)}; inspect the table above")
        pick[tk] = int(c[0])
    return pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    db = wrds.Connection()
    etf = etf_permnos(db)
    print("ETF permnos:", etf)
    if a.check:
        print(db.raw_sql(f"select extract(year from dlycaldt) as year, count(distinct permno) as airlines from crsp.dsf_v2 "
                         f"where siccd = 4512 and {COMMON} and dlycaldt between '{START}' and '{END}' group by 1 order by 1").to_string(index=False))
        print(db.raw_sql(f"select permno, ticker, min(dlycaldt) as first, max(dlycaldt) as last from crsp.dsf_v2 where siccd = 4512 and {COMMON} "
                         f"and dlycaldt between '{START}' and '{END}' group by permno, ticker order by first").to_string(index=False))
        print(db.raw_sql(f"select dlydelflg, count(*) as n from crsp.dsf_v2 where siccd = 4512 and dlycaldt >= '{START}' group by 1").to_string(index=False))
        print(db.raw_sql(f"select permno, ticker, siccd, sharetype, securitytype, dlycaldt, dlyprc, dlyret, dlyretx, dlydelflg from crsp.dsf_v2 "
                         f"where permno in ({QUALIFIED}) and dlycaldt between '{START}' and '{END}' and dlydelflg = 'Y' order by dlycaldt").to_string(index=False))
        print("delisting rows in SIC 4512 outside the universe (expected: ADRs or other share types):")
        print(db.raw_sql(f"select permno, ticker, sharetype, securitytype, usincflg, dlycaldt from crsp.dsf_v2 where siccd = 4512 and "
                         f"dlycaldt >= '{START}' and dlydelflg = 'Y' and permno not in ({QUALIFIED}) order by dlycaldt").to_string(index=False))
        print("gaps of more than two weeks between a stock's rows (treated as an exit, then a new security):")
        print(db.raw_sql(f"select permno, prev_date, dlycaldt as next_date, prev_ticker, ticker, prev_ret from (select permno, ticker, dlycaldt, "
                         f"lag(dlycaldt) over w as prev_date, lag(ticker) over w as prev_ticker, lag(dlyret) over w as prev_ret from crsp.dsf_v2 "
                         f"where permno in ({QUALIFIED}) and dlycaldt between '{START}' and '{END}' window w as (partition by permno order by dlycaldt)) g "
                         f"where dlycaldt - prev_date > 14 order by prev_date").to_string(index=False))
        return
    RAW.mkdir(parents=True, exist_ok=True)
    log = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "etf_permnos": etf, "steps": {}}
    jobs = {
        "airlines.csv": f"select {FIELDS} from crsp.dsf_v2 where permno in ({QUALIFIED}) and dlycaldt between '{START}' and '{END}' order by permno, dlycaldt",
        "etfs.csv": f"select {FIELDS} from crsp.dsf_v2 where permno in ({etf['USO']}, {etf['SPY']}) and dlycaldt between '{START}' and '{END}' order by permno, dlycaldt",
        "ff_daily.csv": f"select date, mktrf, rf from ff.factors_daily where date between '{START}' and '{END}' order by date",
        "ff_monthly.csv": f"select date, rf from ff.factors_monthly where date between '{START}' and '{END}' order by date",
    }
    for fname, q in jobs.items():
        df = db.raw_sql(q)
        p = RAW / fname
        df.to_csv(p, index=False)
        log["steps"][fname] = dict(rows=len(df), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), query=q)
        print(f"{fname}: {len(df)} rows")
    (RAW / "extraction_log.json").write_text(json.dumps(log, indent=2))
    print("wrote data/raw/extraction_log.json")


if __name__ == "__main__":
    main()
