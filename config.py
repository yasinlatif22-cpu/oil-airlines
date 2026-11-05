"""Frozen specification (docs/SPEC.md). Changing any field changes Spec().hash(), which stamps every result."""
import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Spec:
    # signal
    z_lookback: int = 60          # sessions of past USO returns for the volatility estimate (t-60 .. t-1)
    z_threshold: float = 2.0      # event when |z| >= threshold; side = -sign(oil return)
    # basket
    sic: int = 4512               # scheduled air transportation, as recorded by CRSP on each date
    # CRSP permnos in SIC 4512 whose business is not scheduled passenger service; fixed from names before any data was pulled
    # (docs/SPEC.md): Cryoport (life-science cold-chain logistics), Era Group / Bristow (helicopter services, largely for offshore
    # oil and gas), AirNet Systems (air cargo)
    exclude: tuple = (15506, 13743, 83467)
    min_cap: float = 500e6        # market cap at the signal close, dollars
    min_price: float = 5.0
    weight_cap: float = 0.25
    weighting: str = "vw"         # "vw" (primary) | "ew" (declared variant)
    min_names: int = 3
    # hedge
    beta_window: int = 252
    beta_min: float = 0.5
    beta_max: float = 2.0
    # execution
    gross_frac: float = 0.5       # basket notional as a share of equity at the signal close
    fill: str = "open_next"       # "open_next" (primary) | "close_next" (declared variant)
    hold: int = 5                 # sessions between entry and exit fills; 1 and 10 are declared variants
    # frictions (assumptions)
    cost_airline_bps: float = 10.0
    cost_spy_bps: float = 2.0
    borrow_bps: float = 50.0
    initial_equity: float = 1_000_000.0
    # periods (inclusive)
    dev: tuple = ("2007-01-01", "2016-12-31")
    val: tuple = ("2017-01-01", "2021-12-31")
    holdout: tuple = ("2022-01-01", "2025-12-31")

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=list).encode()).hexdigest()[:12]


DEFAULT = Spec()
VARIANTS = {"primary": {}, "hold1": {"hold": 1}, "hold10": {"hold": 10}, "close_fill": {"fill": "close_next"}, "equal_weight": {"weighting": "ew"}}

if __name__ == "__main__":
    print(DEFAULT.hash())
