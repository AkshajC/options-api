import time
import structlog
import httpx

from app.core.config import settings

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.polygon.io"
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # seconds between attempts


def _get(client: httpx.Client, url: str, params: dict) -> dict:
    """GET with retry on 429 rate-limit responses."""
    params = {**params, "apiKey": settings.DATA_PROVIDER_API_KEY}

    for attempt, wait in enumerate(_RETRY_BACKOFF, start=1):
        response = client.get(url, params=params)

        if response.status_code == 429:
            if attempt <= _MAX_RETRIES:
                log.warning(
                    "rate_limit_hit",
                    url=url,
                    attempt=attempt,
                    retry_in=wait,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()

        response.raise_for_status()
        return response.json()

    # unreachable, but satisfies type checkers
    raise RuntimeError("Exceeded retry attempts")  # pragma: no cover


def fetch_options_chain(ticker: str) -> list[dict]:
    """
    Fetch the full options chain snapshot for *ticker* from Polygon.io.

    Paginates automatically and returns all contract snapshots as a flat list.
    Each item is the raw dict from Polygon's /v3/snapshot/options response.

    Raises:
        httpx.HTTPStatusError: on non-retryable HTTP errors.
    """
    ticker = ticker.upper()
    url = f"{_BASE_URL}/v3/snapshot/options/{ticker}"
    params: dict = {"limit": 250}
    results: list[dict] = []

    with httpx.Client(timeout=15.0) as client:
        log.info("fetch_options_chain.start", ticker=ticker)

        while url:
            data = _get(client, url, params)

            results.extend(data.get("results", []))

            # Polygon returns a next_url for pagination; it already contains
            # all query params, so we clear params for subsequent requests.
            url = data.get("next_url", "")
            params = {}

        log.info("fetch_options_chain.done", ticker=ticker, contracts=len(results))

    return results
