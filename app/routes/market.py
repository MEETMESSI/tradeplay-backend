from fastapi import (
    APIRouter,
    Depends,
)

from sqlalchemy.orm import Session

import yfinance as yf

from app.services.market_service import (
    search_stocks,
    get_stock_quote,
    get_company_profile,
    get_stock_history,
    get_market_overview,
)

from app.db.database import SessionLocal

from app.models.watchlist import Watchlist
from app.models.user import User

from app.core.dependencies import (
    get_current_user,
)

router = APIRouter()


# =========================================================
# DATABASE
# =========================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# DEFAULT WATCHLIST
# =========================================================

watch_symbols = [
    "AAPL",
    "TSLA",
    "NVDA",
    "AMZN",
    "META",
    "MSFT",
]


# =========================================================
# YAHOO FINANCE MARKET DATA
#
# Watchlist and Market Movers use one batched Yahoo request.
# This keeps routine dashboard polling away from Twelve Data.
# =========================================================

def get_yfinance_watchlist_data(symbols):

    if not symbols:
        return []

    symbols = [
        str(symbol).upper().strip()
        for symbol in symbols
        if symbol
    ]

    if not symbols:
        return []

    results = {
        symbol: {
            "symbol": symbol,
            "price": 0,
            "change": 0,
        }
        for symbol in symbols
    }

    try:

        data = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

        if data is None or data.empty:
            return list(results.values())

        for symbol in symbols:

            try:

                # Multi-symbol download
                if hasattr(data.columns, "levels"):

                    if symbol not in data.columns.levels[0]:
                        continue

                    symbol_data = data[symbol]

                else:

                    # Single-symbol download
                    symbol_data = data

                if symbol_data is None or symbol_data.empty:
                    continue

                closes = symbol_data["Close"].dropna()

                if closes.empty:
                    continue

                current_price = float(closes.iloc[-1])

                if len(closes) >= 2:

                    previous_price = float(closes.iloc[-2])

                    if previous_price != 0:

                        change_percent = (
                            (
                                current_price
                                - previous_price
                            )
                            / previous_price
                        ) * 100

                    else:
                        change_percent = 0

                else:
                    change_percent = 0

                results[symbol] = {
                    "symbol": symbol,
                    "price": round(current_price, 4),
                    "change": round(change_percent, 2),
                }

            except Exception as e:

                print(
                    "YFINANCE SYMBOL ERROR:",
                    symbol,
                    e,
                )

        return [
            results[symbol]
            for symbol in symbols
        ]

    except Exception as e:

        print(
            "YFINANCE MARKET DATA ERROR:",
            e,
        )

        return [
            results[symbol]
            for symbol in symbols
        ]


# =========================================================
# MARKET OVERVIEW
# =========================================================

@router.get("/overview")
def market_overview():

    try:

        return get_market_overview()

    except Exception as e:

        print(
            "MARKET OVERVIEW ROUTE ERROR:",
            e,
        )

        return []


# =========================================================
# MARKET MOVERS
#
# IMPORTANT:
# Uses Yahoo Finance instead of Twelve Data so normal page
# visits do not consume 15 Twelve Data symbol credits.
# =========================================================

@router.get("/movers")
def market_movers():

    mover_symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "AVGO",
        "AMD",
        "NFLX",
        "JPM",
        "V",
        "MA",
        "WMT",
        "COST",
    ]

    try:

        stocks = get_yfinance_watchlist_data(
            mover_symbols
        )

        valid_stocks = [
            stock
            for stock in stocks
            if stock.get("price", 0) > 0
        ]

        gainers = sorted(
            valid_stocks,
            key=lambda item: item.get(
                "change",
                0,
            ),
            reverse=True,
        )[:5]

        losers = sorted(
            valid_stocks,
            key=lambda item: item.get(
                "change",
                0,
            ),
        )[:5]

        return {
            "gainers": gainers,
            "losers": losers,
        }

    except Exception as e:

        print(
            "MARKET MOVERS ROUTE ERROR:",
            e,
        )

        return {
            "gainers": [],
            "losers": [],
        }


# =========================================================
# DEFAULT WATCHLIST
# =========================================================

@router.get("/watchlist")
def get_watchlist():

    return get_yfinance_watchlist_data(
        watch_symbols
    )


# =========================================================
# ADD TO USER WATCHLIST
# =========================================================

@router.post(
    "/watchlist/add/{symbol}"
)
def add_to_watchlist(

    symbol: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    symbol = symbol.upper().strip()

    existing = (
        db.query(Watchlist)
        .filter(
            Watchlist.user_id
            == current_user.id,

            Watchlist.symbol
            == symbol,
        )
        .first()
    )

    if existing:

        return {
            "message":
                "Already exists"
        }

    item = Watchlist(

        user_id=
            current_user.id,

        symbol=
            symbol,

    )

    db.add(item)

    db.commit()

    return {
        "message":
            "Added"
    }


# =========================================================
# QUOTE
# =========================================================

@router.get(
    "/quote/{symbol}"
)
def get_quote(
    symbol: str,
):

    try:

        return get_stock_quote(
            symbol.upper()
        )

    except Exception as e:

        print(
            "QUOTE ROUTE ERROR:",
            symbol,
            e,
        )

        return {
            "symbol":
                symbol.upper(),

            "price":
                None,

            "error":
                "Market data temporarily unavailable",
        }


# =========================================================
# SEARCH
# =========================================================

@router.get(
    "/search"
)
def search_market(
    query: str,
):

    try:

        return search_stocks(
            query.strip()
        )

    except Exception as e:

        print(
            "SEARCH ROUTE ERROR:",
            query,
            e,
        )

        return []


# =========================================================
# COMPANY PROFILE
# =========================================================

@router.get(
    "/profile/{symbol}"
)
def get_profile(
    symbol: str,
):

    try:

        return get_company_profile(
            symbol.upper()
        )

    except Exception as e:

        print(
            "PROFILE ROUTE ERROR:",
            symbol,
            e,
        )

        return {
            "symbol":
                symbol.upper(),

            "error":
                "Company profile temporarily unavailable",
        }


# =========================================================
# STOCK HISTORY
# =========================================================

@router.get(
    "/history/{symbol}"
)
def get_history(
    symbol: str,
):

    try:

        return get_stock_history(
            symbol.upper()
        )

    except Exception as e:

        print(
            "HISTORY ROUTE ERROR:",
            symbol,
            e,
        )

        return []


# =========================================================
# USER WATCHLIST
# =========================================================

@router.get(
    "/watchlist/user"
)
def get_user_watchlist(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    items = (
        db.query(
            Watchlist
        )
        .filter(
            Watchlist.user_id
            == current_user.id
        )
        .all()
    )

    return [

        {
            "id":
                item.id,

            "symbol":
                item.symbol,
        }

        for item in items

    ]


# =========================================================
# USER WATCHLIST LIVE
#
# Uses the same batched Yahoo Finance path as the default
# watchlist. No individual Twelve Data quote calls.
# =========================================================

@router.get(
    "/watchlist/live"
)
def get_user_watchlist_live(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    items = (
        db.query(
            Watchlist
        )
        .filter(
            Watchlist.user_id
            == current_user.id
        )
        .all()
    )

    symbols = [
        item.symbol
        for item in items
    ]

    return get_yfinance_watchlist_data(
        symbols
    )


# =========================================================
# REMOVE FROM WATCHLIST
# =========================================================

@router.delete(
    "/watchlist/remove/{symbol}"
)
def remove_from_watchlist(

    symbol: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    symbol = symbol.upper().strip()

    item = (
        db.query(
            Watchlist
        )
        .filter(

            Watchlist.user_id
            == current_user.id,

            Watchlist.symbol
            == symbol,

        )
        .first()
    )

    if not item:

        return {
            "message":
                "Not found"
        }

    db.delete(item)

    db.commit()

    return {
        "message":
            "Removed"
    }
