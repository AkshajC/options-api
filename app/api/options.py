from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func
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


@router.get("/history", response_model=list[OptionsContractSchema])
def get_options_history(
    ticker: str = Query(..., description="Underlying ticker symbol, e.g. AAPL"),
    start_date: date = Query(..., description="Start of snapshot window (YYYY-MM-DD), inclusive"),
    end_date: date = Query(default_factory=date.today, description="End of snapshot window (YYYY-MM-DD), inclusive. Defaults to today."),
    db: Session = Depends(get_db),
):
    start_dt = datetime(start_date.year, start_date.month, start_date.day)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    return (
        db.query(OptionsContract)
        .filter(
            OptionsContract.ticker == ticker.upper(),
            OptionsContract.snapshot_time >= start_dt,
            OptionsContract.snapshot_time <= end_dt,
        )
        .order_by(OptionsContract.snapshot_time, OptionsContract.strike_price)
        .all()
    )


@router.get("/summary")
def get_options_summary(
    ticker: str = Query(..., description="Underlying ticker symbol, e.g. AAPL"),
    db: Session = Depends(get_db),
):
    ticker = ticker.upper()
    base = db.query(OptionsContract).filter(OptionsContract.ticker == ticker)

    total_contracts = base.count()
    if total_contracts == 0:
        return {
            "ticker": ticker,
            "total_contracts": 0,
            "call_count": 0,
            "put_count": 0,
            "put_call_ratio": None,
            "avg_implied_volatility": None,
            "avg_delta": None,
            "max_volume_contract": None,
            "available_expiries": [],
        }

    call_count = base.filter(OptionsContract.option_type == "call").count()
    put_count = base.filter(OptionsContract.option_type == "put").count()

    put_call_ratio = round(put_count / call_count, 2) if call_count > 0 else None

    avg_iv = db.query(func.avg(OptionsContract.implied_volatility)).filter(
        OptionsContract.ticker == ticker,
        OptionsContract.implied_volatility.isnot(None),
    ).scalar()

    avg_delta = db.query(func.avg(OptionsContract.delta)).filter(
        OptionsContract.ticker == ticker,
        OptionsContract.delta.isnot(None),
    ).scalar()

    max_vol_row = (
        base.filter(OptionsContract.volume.isnot(None))
        .order_by(OptionsContract.volume.desc())
        .first()
    )

    expiries = (
        db.query(distinct(OptionsContract.expiry_date))
        .filter(OptionsContract.ticker == ticker)
        .order_by(OptionsContract.expiry_date)
        .all()
    )

    return {
        "ticker": ticker,
        "total_contracts": total_contracts,
        "call_count": call_count,
        "put_count": put_count,
        "put_call_ratio": put_call_ratio,
        "avg_implied_volatility": round(float(avg_iv), 4) if avg_iv is not None else None,
        "avg_delta": round(float(avg_delta), 4) if avg_delta is not None else None,
        "max_volume_contract": max_vol_row.contract_symbol if max_vol_row else None,
        "available_expiries": [exp[0].strftime("%Y-%m-%d") for exp in expiries],
    }
