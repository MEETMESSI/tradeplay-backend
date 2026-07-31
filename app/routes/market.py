from app.services.market_service import (
    search_stocks,
    get_stock_quote,
    get_company_profile,
    get_stock_history,
)
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.watchlist import Watchlist
from app.models.user import User
from app.core.dependencies import get_current_user
from fastapi import APIRouter
import yfinance as yf

router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
watch_symbols = [
    "AAPL",
    "TSLA",
    "NVDA",
    "AMZN",
    "META",
    "MSFT",
]


@router.get("/watchlist")
def get_watchlist():

    stocks = []

    for symbol in watch_symbols:

        stock = yf.Ticker(symbol)

        info = stock.info

        price = info.get("currentPrice", 0)
        previous = info.get("previousClose", 0)

        change = 0

        if previous:
            change = ((price - previous) / previous) * 100

        stocks.append({
            "symbol": symbol,
            "price": price,
            "change": round(change, 2)
        })

    return stocks
@router.post("/watchlist/add/{symbol}")
def add_to_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.symbol == symbol.upper()
    ).first()

    if existing:
        return {"message": "Already exists"}

    item = Watchlist(
        user_id=current_user.id,
        symbol=symbol.upper()
    )

    db.add(item)
    db.commit()

    return {"message": "Added"}

@router.get("/quote/{symbol}")
def get_quote(symbol: str):
    return get_stock_quote(symbol)

@router.get("/search")
def search_market(query: str):

    return search_stocks(query)

@router.get("/watchlist/user")
def get_user_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).all()

    return [
        {
            "id": item.id,
            "symbol": item.symbol
        }
        for item in items
    ]
@router.get("/watchlist/live")
def get_user_watchlist_live(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).all()

    stocks = []

    for item in items:

        symbol = item.symbol

        try:
            stock = yf.Ticker(symbol)

            info = stock.info

            price = info.get("currentPrice", 0)
            previous = info.get("previousClose", 0)

            change = 0

            if previous:
                change = (
                    (price - previous)
                    / previous
                ) * 100

            stocks.append({
                "symbol": symbol,
                "price": price,
                "change": round(change, 2)
            })

        except Exception:
            pass

    return stocks

@router.delete("/watchlist/remove/{symbol}")
def remove_from_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.symbol == symbol.upper()
    ).first()

    if not item:
        return {"message": "Not found"}

    db.delete(item)
    db.commit()

    return {"message": "Removed"}

@router.get("/profile/{symbol}")
def get_profile(symbol: str):
    return get_company_profile(symbol)

@router.get("/history/{symbol}")
def get_history(symbol: str):
    return get_stock_history(symbol)