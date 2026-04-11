import math
import time
from datetime import datetime

import structlog
import yfinance as yf

log = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # seconds between attempts


def _or_none(val) -> float | int | None:
    """Convert pandas NaN / inf to None so values are DB-safe."""
    try:
        return None if math.isnan(float(val)) else val
    except (TypeError, ValueError):
        return None


def _fetch_chain_with_retry(yticker: yf.Ticker, expiry: str) -> object:
    """Call option_chain with simple retry on transient failures."""
    last_exc: Exception | None = None
    for attempt, wait in enumerate(_RETRY_BACKOFF, start=1):
        try:
            return yticker.option_chain(expiry)
        except Exception as exc:
            last_exc = exc
            log.warning(
                "fetch_chain.retry",
                expiry=expiry,
                attempt=attempt,
                error=str(exc),
                retry_in=wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch chain after {_MAX_RETRIES} attempts") from last_exc


def fetch_stock_price(ticker: str) -> float | None:
    """Return the last traded price for *ticker*, or None on failure."""
    try:
        price = yf.Ticker(ticker.upper()).fast_info.last_price
        return float(price) if price is not None else None
    except Exception as exc:
        log.warning("fetch_stock_price.error", ticker=ticker, error=str(exc))
        return None


def fetch_options_chain(ticker: str) -> list[dict]:
    """
    Fetch the full options chain for *ticker* via yfinance.

    Iterates over every available expiration date and combines calls and puts
    into a flat list of dicts. Keys match the OptionsContract model fields;
    fields not available from yfinance (greeks, is_live) are omitted so the
    caller can apply its own defaults.

    Raises:
        RuntimeError: if all retry attempts for any expiration are exhausted.
    """
    ticker = ticker.upper()
    yticker = yf.Ticker(ticker)

    expiry_dates: tuple[str, ...] = yticker.options
    if not expiry_dates:
        log.warning("fetch_options_chain.no_expirations", ticker=ticker)
        return []

    log.info("fetch_options_chain.start", ticker=ticker, expirations=len(expiry_dates))
    results: list[dict] = []

    for expiry in expiry_dates:
        expiry_date = datetime.fromisoformat(expiry)
        chain = _fetch_chain_with_retry(yticker, expiry)

        for df, option_type in [(chain.calls, "call"), (chain.puts, "put")]:
            for row in df.itertuples(index=False):
                results.append(
                    dict(
                        ticker=ticker,
                        contract_symbol=row.contractSymbol,
                        option_type=option_type,
                        strike_price=_or_none(row.strike),
                        expiry_date=expiry_date,
                        bid=_or_none(row.bid),
                        ask=_or_none(row.ask),
                        last_price=_or_none(row.lastPrice),
                        volume=_or_none(row.volume),
                        open_interest=_or_none(row.openInterest),
                        implied_volatility=_or_none(row.impliedVolatility),
                    )
                )

    log.info("fetch_options_chain.done", ticker=ticker, contracts=len(results))
    return results
