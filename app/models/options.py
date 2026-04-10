from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OptionsContract(Base):
    __tablename__ = "options_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    contract_symbol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    option_type: Mapped[str] = mapped_column(String, nullable=False)  # "call" or "put"
    strike_price: Mapped[float] = mapped_column(Float, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    implied_volatility: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)
    gamma: Mapped[float | None] = mapped_column(Float)
    theta: Mapped[float | None] = mapped_column(Float)
    vega: Mapped[float | None] = mapped_column(Float)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WatchedTicker(Base):
    __tablename__ = "watched_tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
