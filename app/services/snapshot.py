import math
from datetime import datetime, time
from zoneinfo import ZoneInfo

import structlog
from scipy.stats import norm

from app.core.database import SessionLocal
from app.models.options import OptionsContract, WatchedTicker
from app.services.fetcher import fetch_options_chain, fetch_stock_price

log = structlog.get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)
_RISK_FREE_RATE = 0.043


def _is_market_hours() -> bool:
    now = datetime.now(_ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now.time() < _MARKET_CLOSE


def calculate_greeks(
    option_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
) -> dict:
    """
    Black-Scholes greeks for a European option.

    S     — underlying price
    K     — strike price
    T     — time to expiry in years
    r     — risk-free rate (annualised)
    sigma — implied volatility (annualised)

    Returns delta, gamma, theta (per calendar day), vega (per 1% IV move).
    Returns all zeros when T or sigma are non-positive.
    """
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    npdf_d1 = norm.pdf(d1)

    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (
            -S * npdf_d1 * sigma / (2 * sqrt_T)
            - r * K * math.exp(-r * T) * norm.cdf(d2)
        ) / 365
    else:
        delta = norm.cdf(d1) - 1
        theta = (
            -S * npdf_d1 * sigma / (2 * sqrt_T)
            + r * K * math.exp(-r * T) * norm.cdf(-d2)
        ) / 365

    gamma = npdf_d1 / (S * sigma * sqrt_T)
    vega = S * npdf_d1 * sqrt_T / 100

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega),
    }


def _map_contract(
    ticker: str,
    raw: dict,
    snapshot_time: datetime,
    stock_price: float | None,
) -> dict:
    greeks = {"delta": None, "gamma": None, "theta": None, "vega": None}

    expiry_date = raw.get("expiry_date")
    iv = raw.get("implied_volatility")
    strike = raw.get("strike_price")
    option_type = raw.get("option_type")

    if stock_price is not None and expiry_date is not None and iv is not None and strike is not None and option_type is not None:
        T = (expiry_date - snapshot_time).days / 365
        greeks = calculate_greeks(option_type, stock_price, strike, T, _RISK_FREE_RATE, iv)

    return {
        **raw,
        "ticker": ticker,
        "snapshot_time": snapshot_time,
        **greeks,
        "is_live": raw.get("is_live", False),
    }


def _upsert_contracts(
    db,
    ticker: str,
    raw_contracts: list[dict],
    snapshot_time: datetime,
    stock_price: float | None,
) -> int:
    count = 0
    for raw in raw_contracts:
        fields = _map_contract(ticker, raw, snapshot_time, stock_price)
        symbol = fields["contract_symbol"]
        if not symbol:
            continue

        row = db.query(OptionsContract).filter_by(contract_symbol=symbol).first()
        if row:
            for k, v in fields.items():
                setattr(row, k, v)
        else:
            db.add(OptionsContract(**fields))
        count += 1

    db.commit()
    return count


def run_snapshot_job() -> None:
    if not _is_market_hours():
        log.debug("snapshot_job.skipped", reason="outside market hours")
        return

    db = SessionLocal()
    try:
        tickers = [
            row.ticker
            for row in db.query(WatchedTicker).filter_by(is_active=True).all()
        ]
    finally:
        db.close()

    if not tickers:
        log.debug("snapshot_job.skipped", reason="no active tickers")
        return

    log.info("snapshot_job.start", tickers=tickers)
    snapshot_time = datetime.utcnow()

    for ticker in tickers:
        db = SessionLocal()
        try:
            stock_price = fetch_stock_price(ticker)
            raw_contracts = fetch_options_chain(ticker)
            written = _upsert_contracts(db, ticker, raw_contracts, snapshot_time, stock_price)
            log.info("snapshot_job.ticker_done", ticker=ticker, written=written, stock_price=stock_price)
        except Exception:
            log.exception("snapshot_job.ticker_error", ticker=ticker)
        finally:
            db.close()
