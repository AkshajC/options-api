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
    """Merge fetcher output with fields the fetcher does not provide."""
    return {
        **raw,
        "ticker": ticker,
        "snapshot_time": snapshot_time,
        # yfinance does not supply greeks or a live-quote flag
        "delta": raw.get("delta"),
        "gamma": raw.get("gamma"),
        "theta": raw.get("theta"),
        "vega": raw.get("vega"),
        "is_live": raw.get("is_live", False),
    }


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
