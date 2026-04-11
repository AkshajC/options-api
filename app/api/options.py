from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.options import OptionsContract
from app.schemas.options import OptionsContractSchema

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/chain", response_model=list[OptionsContractSchema])
def get_options_chain(
    ticker: str = Query(..., description="Underlying ticker symbol, e.g. AAPL"),
    expiry: date | None = Query(None, description="Filter to a single expiration date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    q = db.query(OptionsContract).filter(OptionsContract.ticker == ticker.upper())

    if expiry is not None:
        q = q.filter(OptionsContract.expiry_date == expiry)

    return q.order_by(OptionsContract.expiry_date, OptionsContract.strike_price).all()


@router.get("/filter", response_model=list[OptionsContractSchema])
def filter_options(
    ticker: str | None = Query(None, description="Comma-separated ticker symbols, e.g. AAPL,TSLA"),
    option_type: str | None = Query(None, pattern="^(call|put)$", description="call or put"),
    min_strike: float | None = Query(None, ge=0),
    max_strike: float | None = Query(None, ge=0),
    min_volume: int | None = Query(None, ge=0),
    min_open_interest: int | None = Query(None, ge=0),
    min_iv: float | None = Query(None, ge=0),
    max_iv: float | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(OptionsContract)

    if ticker is not None:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        q = q.filter(OptionsContract.ticker.in_(tickers))
    if option_type is not None:
        q = q.filter(OptionsContract.option_type == option_type)
    if min_strike is not None:
        q = q.filter(OptionsContract.strike_price >= min_strike)
    if max_strike is not None:
        q = q.filter(OptionsContract.strike_price <= max_strike)
    if min_volume is not None:
        q = q.filter(OptionsContract.volume >= min_volume)
    if min_open_interest is not None:
        q = q.filter(OptionsContract.open_interest >= min_open_interest)
    if min_iv is not None:
        q = q.filter(OptionsContract.implied_volatility >= min_iv)
    if max_iv is not None:
        q = q.filter(OptionsContract.implied_volatility <= max_iv)

    return q.order_by(OptionsContract.ticker, OptionsContract.expiry_date, OptionsContract.strike_price).all()
