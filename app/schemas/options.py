from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OptionsContractSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    contract_symbol: str
    option_type: str
    strike_price: float
    expiry_date: datetime
    bid: float | None
    ask: float | None
    last_price: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    snapshot_time: datetime
    is_live: bool
