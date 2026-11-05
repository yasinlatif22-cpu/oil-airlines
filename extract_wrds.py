"""Pull the licensed data from WRDS on your own machine. Credentials are entered interactively and never stored by this code.

  python extract_wrds.py --check     # coverage, the airline universe by year, USO/SPY identifiers, delisting flags; no prices saved
  python extract_wrds.py             # writes data/raw/*.csv and data/raw/extraction_log.json (git-ignored; do not publish)

Universe: CRSP CIZ daily rows (crsp.dsf_v2) recorded with SIC 4512 and common-stock attributes on that date, 2005-06 to 2025-12,
so membership is point-in-time. USO and SPY are found by ticker and issuer name and pulled without the common-stock filter."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import wrds

START, END = "2005-06-01", "2025-12-31"
COMMON = "sharetype = 'NS' and securitytype = 'EQTY' and securitysubtype = 'COM' and usincflg = 'Y' and primaryexch in ('N', 'A', 'Q')"
FIELDS = "permno, ticker, siccd, dlycaldt, dlyprc, dlyopen, dlyclose, dlyret, dlyretx, dlycumfacpr, dlycap, shrout, dlydelflg"
RAW = Path("data/raw")


def etf_permnos(db):
    q = ("select distinct permno, ticker, issuernm, securitybegdt, securityenddt from crsp.stksecurityinfohist "
         "where ticker in ('USO', 'SPY')")
    df = db.raw_sql(q)
    print(df.to_string(index=False))
    pick = {}
    for tk, name in (("USO", "UNITED STATES OIL"), ("SPY", "SPDR S&P 500")):
        c = df[(df.ticker == tk) & df.issuernm.str.upper().str.contains(name, na=False)].permno.unique()
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
        print(db.raw_sql(f"select permno, ticker, dlycaldt, dlyprc, dlyret, dlyretx, dlydelflg from crsp.dsf_v2 where siccd = 4512 and {COMMON} "
                         f"and dlycaldt between '{START}' and '{END}' and dlydelflg <> 'N' order by dlycaldt").to_string(index=False))
        return
    RAW.mkdir(parents=True, exist_ok=True)
    log = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "etf_permnos": etf, "steps": {}}
    jobs = {
        "airlines.csv": f"select {FIELDS} from crsp.dsf_v2 where siccd = 4512 and {COMMON} and dlycaldt between '{START}' and '{END}' order by permno, dlycaldt",
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
