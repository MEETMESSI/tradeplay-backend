from pydantic import BaseModel

class TradeCreate(BaseModel):
    symbol: str
    quantity: float
    side: str