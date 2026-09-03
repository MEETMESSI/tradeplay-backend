from typing import Optional

from pydantic import BaseModel


class TradeCreate(BaseModel):

    symbol: str

    quantity: float

    side: str

    order_type: str = "MARKET"

    limit_price: Optional[float] = None

    stop_price: Optional[float] = None