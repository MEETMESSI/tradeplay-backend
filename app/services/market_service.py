import os
import requests

API_KEY = os.getenv("FMP_API_KEY")

BASE_URL = "https://financialmodelingprep.com/stable"


def search_stocks(query: str):
    try:
        response = requests.get(
            f"{BASE_URL}/search-symbol",
            params={
                "query": query,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return [
            {
                "symbol": stock.get("symbol"),
                "name": stock.get("name"),
                "exchange": stock.get("exchange"),
                "currency": stock.get("currency"),
            }
            for stock in data
        ]

    except Exception as e:
        print("SEARCH ERROR:", e)
        return []


def get_stock_quote(symbol: str):
    try:
        quote_response = requests.get(
            f"{BASE_URL}/quote",
            params={
                "symbol": symbol,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        quote_response.raise_for_status()

        quote_data = quote_response.json()

        if not quote_data:
            return {}

        stock = quote_data[0]

        profile_response = requests.get(
            f"{BASE_URL}/profile",
            params={
                "symbol": symbol,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        profile = {}

        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            if profile_data:
                profile = profile_data[0]

        range_52 = profile.get("range", "")

        low52 = None
        high52 = None

        if range_52 and "-" in range_52:
            parts = range_52.split("-")
            low52 = parts[0].strip()
            high52 = parts[1].strip()

        return {
            "symbol": stock.get("symbol"),
            "company": stock.get("name"),
            "price": stock.get("price"),
            "change": stock.get("change"),
            "changePercent": stock.get("changesPercentage"),
            "volume": stock.get("volume"),
            "marketCap": profile.get("mktCap"),
            "pe": profile.get("pe"),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "high52": high52,
            "low52": low52,
        }

    except Exception as e:
        print("QUOTE ERROR:", e)
        return {}


def get_company_profile(symbol: str):
    try:
        response = requests.get(
            f"{BASE_URL}/profile",
            params={
                "symbol": symbol,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return {}

        company = data[0]

        return {
            "symbol": company.get("symbol"),
            "company": company.get("companyName"),
            "logo": company.get("image"),
            "website": company.get("website"),
            "sector": company.get("sector"),
            "industry": company.get("industry"),
            "country": company.get("country"),
            "exchange": company.get("exchangeShortName"),
            "ceo": company.get("ceo"),
            "employees": company.get("fullTimeEmployees"),
            "description": company.get("description"),
        }

    except Exception as e:
        print("PROFILE ERROR:", e)
        return {}


def get_stock_history(symbol: str):
    try:
        response = requests.get(
            f"{BASE_URL}/historical-price-full",
            params={
                "symbol": symbol,
                "timeseries": 365,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        history = data.get("historical", [])

        return [
            {
                "date": candle.get("date"),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "volume": candle.get("volume"),
            }
            for candle in history
        ]

    except Exception as e:
        print("HISTORY ERROR:", e)
        return []

def get_stock_price(symbol: str):
    try:
        response = requests.get(
            f"{BASE_URL}/quote",
            params={
                "symbol": symbol,
                "apikey": API_KEY,
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        return data[0].get("price")

    except Exception as e:
        print("PRICE ERROR:", e)
        return None    