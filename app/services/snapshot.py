from datetime import datetime, time
from zoneinfo import ZoneInfo

import structlog

from app.core.database import SessionLocal
from app.models.options import OptionsContract, WatchedTicker
from app.services.fetcher import fetch_options_chain

log = structlog.get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)


def _is_market_hours() -> bool:
    now = datetime.now(_ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now.time() < _MARKET_CLOSE


def _map_contract(ticker: str, raw: dict, snapshot_time: datetime) -> dict:
    """Extract fields from a Polygon /v3/snapshot/options result dict."""
    details = raw.get("details", {})
    greeks = raw.get("greeks", {})
    last_quote = raw.get("last_quote", {})
    last_trade = raw.get("last_trade", {})
    day = raw.get("day", {})

    return dict(
        ticker=ticker,
        contract_symbol=details.get("ticker", ""),
        option_type=details.get("contract_type", ""),
        strike_price=details.get("strike_price"),
        expiry_date=datetime.fromisoformat(details["expiration_date"]),
        bid=last_quote.get("bid"),
        ask=last_quote.get("ask"),
        last_price=last_trade.get("price"),
        volume=day.get("volume"),
        open_interest=raw.get("open_interest"),
        implied_volatility=raw.get("implied_volatility"),
        delta=greeks.get("delta"),
        gamma=greeks.get("gamma"),
        theta=greeks.get("theta"),
        vega=greeks.get("vega"),
        snapshot_time=snapshot_time,
        is_live=last_quote.get("timeframe") == "REAL-TIME",
    )


def _upsert_contracts(db, ticker: str, raw_contracts: list[dict], snapshot_time: datetime) -> int:
    count = 0
    for raw in raw_contracts:
        fields = _map_contract(ticker, raw, snapshot_time)
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
            raw_contracts = fetch_options_chain(ticker)
            written = _upsert_contracts(db, ticker, raw_contracts, snapshot_time)
            log.info("snapshot_job.ticker_done", ticker=ticker, written=written)
        except Exception:
            log.exception("snapshot_job.ticker_error", ticker=ticker)
        finally:
            db.close()
