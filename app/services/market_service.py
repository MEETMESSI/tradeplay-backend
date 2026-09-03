import os
import time
import threading

import requests
import yfinance as yf

from dotenv import load_dotenv


load_dotenv()


# =========================================================
# CONFIG
# =========================================================

API_KEY = os.getenv(
    "TWELVE_DATA_API_KEY"
)


BASE_URL = (
    "https://api.twelvedata.com"
)


REQUEST_TIMEOUT_SECONDS = 10


# =========================================================
# CACHE
# =========================================================

_price_cache = {}
_quote_cache = {}
_history_cache = {}
_profile_cache = {}
_market_overview_cache = {}
_market_movers_cache = {}
_search_cache = {}


# =========================================================
# CACHE DURATIONS
# =========================================================

PRICE_CACHE_SECONDS = 120

QUOTE_CACHE_SECONDS = 300

HISTORY_CACHE_SECONDS = 3600

PROFILE_CACHE_SECONDS = 86400

MARKET_OVERVIEW_CACHE_SECONDS = 300

MARKET_MOVERS_CACHE_SECONDS = 300

SEARCH_CACHE_SECONDS = 600


# =========================================================
# REQUEST DEDUPLICATION
#
# Prevent multiple requests for the same data at the same
# time from creating duplicate Twelve Data API calls.
# =========================================================

_cache_lock = threading.Lock()

_inflight_requests = {}


# =========================================================
# RATE LIMIT PROTECTION
# =========================================================

_rate_limit_until = 0

RATE_LIMIT_COOLDOWN_SECONDS = 120


# =========================================================
# HTTP SESSION
#
# Reuse HTTP connections instead of creating a new connection
# for every market request.
# =========================================================

_session = requests.Session()


# =========================================================
# HELPERS
# =========================================================

def _to_float(
    value,
):
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _normalise_symbol(
    symbol: str,
):
    return (
        symbol
        .upper()
        .strip()
    )


# =========================================================
# CACHE HELPERS
# =========================================================

def _get_cached(
    cache,
    key,
    max_age,
):
    with _cache_lock:

        item = cache.get(
            key
        )

        if not item:
            return None

        timestamp, value = item

        age = (
            time.time()
            - timestamp
        )

        if age > max_age:
            return None

        return value


def _get_stale_cached(
    cache,
    key,
):
    with _cache_lock:

        item = cache.get(
            key
        )

        if not item:
            return None

        _, value = item

        return value


def _set_cached(
    cache,
    key,
    value,
):
    with _cache_lock:

        cache[key] = (
            time.time(),
            value,
        )


# =========================================================
# RATE LIMIT HELPERS
# =========================================================

def _set_rate_limit_cooldown():
    global _rate_limit_until

    _rate_limit_until = (
        time.time()
        + RATE_LIMIT_COOLDOWN_SECONDS
    )

    print(
        "TWELVE DATA RATE LIMIT HIT."
    )

    print(
        f"API requests paused for "
        f"{RATE_LIMIT_COOLDOWN_SECONDS} seconds."
    )


def _is_rate_limited():
    return (
        time.time()
        < _rate_limit_until
    )


# =========================================================
# GENERIC API REQUEST
# =========================================================

def _get(
    endpoint: str,
    params: dict,
):
    global _rate_limit_until

    # -----------------------------------------------------
    # API KEY
    # -----------------------------------------------------

    if not API_KEY:

        raise Exception(
            "TWELVE_DATA_API_KEY is not configured"
        )


    # -----------------------------------------------------
    # RATE LIMIT COOLDOWN
    # -----------------------------------------------------

    now = time.time()

    if now < _rate_limit_until:

        remaining = int(
            _rate_limit_until
            - now
        )

        raise Exception(
            f"Rate limit cooldown active "
            f"({remaining}s remaining)"
        )


    # -----------------------------------------------------
    # REQUEST PARAMETERS
    # -----------------------------------------------------

    request_params = params.copy()

    request_params[
        "apikey"
    ] = API_KEY


    # -----------------------------------------------------
    # REQUEST
    # -----------------------------------------------------

    try:

        response = _session.get(
            f"{BASE_URL}/{endpoint}",
            params=request_params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.RequestException as e:

        raise Exception(
            f"Twelve Data request failed: {e}"
        )


    # -----------------------------------------------------
    # HTTP RATE LIMIT
    # -----------------------------------------------------

    if response.status_code == 429:

        _set_rate_limit_cooldown()

        raise Exception(
            "Twelve Data rate limit reached"
        )


    # -----------------------------------------------------
    # OTHER HTTP ERRORS
    # -----------------------------------------------------

    response.raise_for_status()


    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        raise Exception(
            "Invalid response from Twelve Data"
        )


    # -----------------------------------------------------
    # API ERROR
    # -----------------------------------------------------

    if (
        isinstance(
            data,
            dict,
        )
        and data.get(
            "status"
        )
        == "error"
    ):

        message = data.get(
            "message",
            "Twelve Data API error",
        )


        message_lower = (
            str(message)
            .lower()
        )


        if (
            "limit" in message_lower
            or "quota" in message_lower
            or "frequency" in message_lower
            or "rate" in message_lower
        ):

            _set_rate_limit_cooldown()


        raise Exception(
            message
        )


    return data


# =========================================================
# REQUEST DEDUPLICATION
# =========================================================

def _begin_request(
    key,
):
    with _cache_lock:

        if key in _inflight_requests:

            return False

        _inflight_requests[
            key
        ] = time.time()

        return True


def _end_request(
    key,
):
    with _cache_lock:

        _inflight_requests.pop(
            key,
            None,
        )


# =========================================================
# STOCK SEARCH
# =========================================================

def search_stocks(
    query: str,
):
    if (
        not query
        or not query.strip()
    ):
        return []


    query = (
        query
        .strip()
        .upper()
    )


    cached = _get_cached(
        _search_cache,
        query,
        SEARCH_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    try:

        data = _get(
            "symbol_search",
            {
                "symbol": query,
            },
        )


        results = data.get(
            "data",
            [],
        )


        result = [

            {
                "symbol":
                    stock.get(
                        "symbol"
                    ),

                "name":
                    stock.get(
                        "instrument_name"
                    ),

                "exchange":
                    stock.get(
                        "exchange"
                    ),

                "currency":
                    stock.get(
                        "currency"
                    ),
            }

            for stock in results

        ]


        _set_cached(
            _search_cache,
            query,
            result,
        )


        return result


    except Exception as e:

        print(
            "SEARCH ERROR:",
            e,
        )


        stale = _get_stale_cached(
            _search_cache,
            query,
        )


        if stale is not None:

            return stale


        return []


# =========================================================
# COMPANY PROFILE
# =========================================================

def get_company_profile(
    symbol: str,
):
    symbol = _normalise_symbol(
        symbol
    )


    cached = _get_cached(
        _profile_cache,
        symbol,
        PROFILE_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    try:

        data = _get(
            "profile",
            {
                "symbol": symbol,
            },
        )


        result = {

            "symbol":
                data.get(
                    "symbol"
                ),

            "company":
                data.get(
                    "name"
                ),

            "logo":
                data.get(
                    "logo"
                ),

            "website":
                data.get(
                    "website"
                ),

            "sector":
                data.get(
                    "sector"
                ),

            "industry":
                data.get(
                    "industry"
                ),

            "country":
                data.get(
                    "country"
                ),

            "exchange":
                data.get(
                    "exchange"
                ),

            "currency":
                data.get(
                    "currency"
                ),

            "ceo":
                data.get(
                    "ceo"
                ),

            "employees":
                data.get(
                    "employees"
                ),

            "description":
                data.get(
                    "description"
                ),
        }


        _set_cached(
            _profile_cache,
            symbol,
            result,
        )


        return result


    except Exception as e:

        print(
            "PROFILE ERROR:",
            symbol,
            e,
        )


        stale = _get_stale_cached(
            _profile_cache,
            symbol,
        )


        if stale is not None:

            return stale


        return {}


# =========================================================
# YAHOO FINANCE PRICE FALLBACK / PRIMARY ROUTINE PRICE SOURCE
# =========================================================

def _get_yahoo_price(symbol: str):
    """
    Get the latest available market price from Yahoo Finance.

    This is intentionally used for routine price lookups such as
    portfolio valuation and order execution so those requests do
    not consume Twelve Data API credits.
    """
    yahoo_symbol = symbol.replace("/", "-")

    try:
        data = yf.download(
            tickers=yahoo_symbol,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if data is None or data.empty:
            return None

        close = data["Close"]

        # yfinance may return a DataFrame even for one ticker.
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]

        close = close.dropna()

        if close.empty:
            return None

        return _to_float(close.iloc[-1])

    except Exception as e:
        print("YAHOO PRICE ERROR:", symbol, e)
        return None


# =========================================================
# STOCK PRICE
# =========================================================


def get_stock_price(
    symbol: str,
):
    symbol = _normalise_symbol(
        symbol
    )

    request_key = (
        f"price:{symbol}"
    )

    # -----------------------------------------------------
    # PRICE CACHE
    # -----------------------------------------------------

    cached = _get_cached(
        _price_cache,
        symbol,
        PRICE_CACHE_SECONDS,
    )

    if cached is not None:
        return cached

    # -----------------------------------------------------
    # QUOTE CACHE
    # -----------------------------------------------------

    quote = _get_cached(
        _quote_cache,
        symbol,
        QUOTE_CACHE_SECONDS,
    )

    if (
        quote is not None
        and quote.get(
            "price"
        ) is not None
    ):
        price = quote[
            "price"
        ]

        _set_cached(
            _price_cache,
            symbol,
            price,
        )

        return price

    # -----------------------------------------------------
    # RATE LIMIT FALLBACK
    # -----------------------------------------------------

    if _is_rate_limited():

        stale = _get_stale_cached(
            _price_cache,
            symbol,
        )

        if stale is not None:
            return stale

        stale_quote = _get_stale_cached(
            _quote_cache,
            symbol,
        )

        if (
            stale_quote is not None
            and stale_quote.get(
                "price"
            ) is not None
        ):
            return stale_quote[
                "price"
            ]

        return None

    # -----------------------------------------------------
    # REQUEST DEDUPLICATION
    # -----------------------------------------------------

    if not _begin_request(
        request_key
    ):

        for _ in range(20):

            time.sleep(0.1)

            cached = _get_cached(
                _price_cache,
                symbol,
                PRICE_CACHE_SECONDS,
            )

            if cached is not None:
                return cached

            quote = _get_cached(
                _quote_cache,
                symbol,
                QUOTE_CACHE_SECONDS,
            )

            if (
                quote is not None
                and quote.get(
                    "price"
                ) is not None
            ):
                return quote[
                    "price"
                ]

        stale = _get_stale_cached(
            _price_cache,
            symbol,
        )

        if stale is not None:
            return stale

        stale_quote = _get_stale_cached(
            _quote_cache,
            symbol,
        )

        if (
            stale_quote is not None
            and stale_quote.get(
                "price"
            ) is not None
        ):
            return stale_quote[
                "price"
            ]

        return None

    # -----------------------------------------------------
    # API REQUEST
    # -----------------------------------------------------

    try:

        # Re-check after acquiring the request lock.
        cached = _get_cached(
            _price_cache,
            symbol,
            PRICE_CACHE_SECONDS,
        )

        if cached is not None:
            return cached

        # Avoid calling the API if another request triggered
        # a rate-limit cooldown while this request was waiting.
        if _is_rate_limited():

            stale = _get_stale_cached(
                _price_cache,
                symbol,
            )

            if stale is not None:
                return stale

            stale_quote = _get_stale_cached(
                _quote_cache,
                symbol,
            )

            if (
                stale_quote is not None
                and stale_quote.get(
                    "price"
                ) is not None
            ):
                return stale_quote[
                    "price"
                ]

            return None

        # -----------------------------------------------------
        # PRIMARY ROUTINE PRICE SOURCE: YAHOO FINANCE
        #
        # Portfolio valuation, order execution, and the pending
        # order worker can call get_stock_price() frequently.
        # Using Yahoo here prevents those routine calls from
        # consuming Twelve Data API credits.
        # -----------------------------------------------------

        yahoo_price = _get_yahoo_price(symbol)

        if yahoo_price is not None:
            _set_cached(
                _price_cache,
                symbol,
                yahoo_price,
            )

            return yahoo_price

        # -----------------------------------------------------
        # TWELVE DATA FALLBACK
        #
        # Keep Twelve Data as a fallback if Yahoo is temporarily
        # unavailable. Existing rate-limit protection and stale
        # cache handling still apply.
        # -----------------------------------------------------

        data = _get(
            "price",
            {
                "symbol": symbol,
            },
        )

        price = _to_float(
            data.get(
                "price"
            )
        )

        if price is None:
            return None

        _set_cached(
            _price_cache,
            symbol,
            price,
        )

        return price

    except Exception as e:

        stale = _get_stale_cached(
            _price_cache,
            symbol,
        )

        if stale is not None:
            return stale

        stale_quote = _get_stale_cached(
            _quote_cache,
            symbol,
        )

        if (
            stale_quote is not None
            and stale_quote.get(
                "price"
            ) is not None
        ):
            return stale_quote[
                "price"
            ]

        print(
            "PRICE ERROR:",
            symbol,
            e,
        )

        return None

    finally:

        _end_request(
            request_key
        )

# =========================================================
# STOCK QUOTE
# =========================================================

def get_stock_quote(
    symbol: str,
):
    symbol = _normalise_symbol(
        symbol
    )


    cached = _get_cached(
        _quote_cache,
        symbol,
        QUOTE_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    try:

        data = _get(
            "quote",
            {
                "symbol": symbol,
            },
        )


        fifty_two_week = (
            data.get(
                "fifty_two_week",
                {},
            )
        )


        if not isinstance(
            fifty_two_week,
            dict,
        ):

            fifty_two_week = {}


        # -------------------------------------------------
        # IMPORTANT:
        #
        # Do not automatically fetch profile data for every
        # quote. That was creating an extra API request for
        # every symbol in market overview.
        #
        # Only use profile data if already cached.
        # -------------------------------------------------

        profile = _get_cached(
            _profile_cache,
            symbol,
            PROFILE_CACHE_SECONDS,
        )

        if profile is None:

            profile = {}


        result = {

            "symbol":
                data.get(
                    "symbol"
                )
                or symbol,

            "company":
                data.get(
                    "name"
                )
                or profile.get(
                    "company"
                )
                or symbol,

            "price":
                _to_float(
                    data.get(
                        "close"
                    )
                ),

            "change":
                _to_float(
                    data.get(
                        "change"
                    )
                ),

            "changePercent":
                _to_float(
                    data.get(
                        "percent_change"
                    )
                ),

            "volume":
                _to_float(
                    data.get(
                        "volume"
                    )
                ),

            "marketCap":
                _to_float(
                    data.get(
                        "market_cap"
                    )
                ),

            "pe":
                _to_float(
                    data.get(
                        "pe"
                    )
                ),

            "eps":
                _to_float(
                    data.get(
                        "eps"
                    )
                ),

            "dividendYield":
                _to_float(
                    data.get(
                        "dividend_yield"
                    )
                ),

            "averageVolume":
                _to_float(
                    data.get(
                        "average_volume"
                    )
                ),

            "previousClose":
                _to_float(
                    data.get(
                        "previous_close"
                    )
                ),

            "currency":
                data.get(
                    "currency"
                )
                or profile.get(
                    "currency"
                ),

            "sector":
                profile.get(
                    "sector"
                ),

            "industry":
                profile.get(
                    "industry"
                ),

            "high52":
                _to_float(
                    fifty_two_week.get(
                        "high"
                    )
                ),

            "low52":
                _to_float(
                    fifty_two_week.get(
                        "low"
                    )
                ),

            "exchange":
                data.get(
                    "exchange"
                )
                or profile.get(
                    "exchange"
                ),

            "logo":
                profile.get(
                    "logo"
                ),

            "website":
                profile.get(
                    "website"
                ),

            "country":
                profile.get(
                    "country"
                ),

            "ceo":
                profile.get(
                    "ceo"
                ),

            "employees":
                profile.get(
                    "employees"
                ),

            "description":
                profile.get(
                    "description"
                ),
        }


        _set_cached(
            _quote_cache,
            symbol,
            result,
        )


        if (
            result[
                "price"
            ]
            is not None
        ):

            _set_cached(
                _price_cache,
                symbol,
                result[
                    "price"
                ],
            )


        return result


    except Exception as e:

        print(
            "QUOTE ERROR:",
            symbol,
            e,
        )


        stale = _get_stale_cached(
            _quote_cache,
            symbol,
        )


        if stale is not None:

            return stale


        return {}


# =========================================================
# STOCK HISTORY
# =========================================================

def get_stock_history(
    symbol: str,
):
    symbol = _normalise_symbol(
        symbol
    )


    cached = _get_cached(
        _history_cache,
        symbol,
        HISTORY_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    try:

        data = _get(
            "time_series",
            {
                "symbol":
                    symbol,

                "interval":
                    "1day",

                "outputsize":
                    365,
            },
        )


        values = data.get(
            "values",
            [],
        )


        result = [

            {
                "date":
                    candle.get(
                        "datetime"
                    ),

                "open":
                    _to_float(
                        candle.get(
                            "open"
                        )
                    ),

                "high":
                    _to_float(
                        candle.get(
                            "high"
                        )
                    ),

                "low":
                    _to_float(
                        candle.get(
                            "low"
                        )
                    ),

                "close":
                    _to_float(
                        candle.get(
                            "close"
                        )
                    ),

                "volume":
                    _to_float(
                        candle.get(
                            "volume"
                        )
                    ),
            }

            for candle in values

        ]


        _set_cached(
            _history_cache,
            symbol,
            result,
        )


        return result


    except Exception as e:

        print(
            "HISTORY ERROR:",
            symbol,
            e,
        )


        stale = _get_stale_cached(
            _history_cache,
            symbol,
        )


        if stale is not None:

            return stale


        return []


# =========================================================
# MARKET OVERVIEW
# =========================================================

MARKET_OVERVIEW_SYMBOLS = [

    {
        "symbol": "SPY",
        "name": "S&P 500",
        "type": "ETF",
    },

    {
        "symbol": "QQQ",
        "name": "Nasdaq 100",
        "type": "ETF",
    },

    {
        "symbol": "DIA",
        "name": "Dow Jones",
        "type": "ETF",
    },

    {
        "symbol": "GLD",
        "name": "Gold",
        "type": "ETF",
    },

    {
        "symbol": "USO",
        "name": "Crude Oil",
        "type": "ETF",
    },

    {
        "symbol": "BTC/USD",
        "name": "Bitcoin",
        "type": "Crypto",
    },

]


def get_market_overview():

    cache_key = (
        "market_overview"
    )


    cached = _get_cached(
        _market_overview_cache,
        cache_key,
        MARKET_OVERVIEW_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    results = []


    # -----------------------------------------------------
    # Try one batch request first.
    #
    # This replaces multiple individual quote requests.
    # -----------------------------------------------------

    try:

        symbols = ",".join(
            [
                item[
                    "symbol"
                ]
                for item
                in MARKET_OVERVIEW_SYMBOLS
            ]
        )


        data = _get(
            "quote",
            {
                "symbol":
                    symbols,
            },
        )


        for item in MARKET_OVERVIEW_SYMBOLS:

            symbol = item[
                "symbol"
            ]


            quote = data.get(
                symbol,
                {}
            )


            if not isinstance(
                quote,
                dict,
            ):

                quote = {}


            price = _to_float(
                quote.get(
                    "close"
                )
            )


            result = {

                "symbol":
                    symbol,

                "name":
                    item[
                        "name"
                    ],

                "type":
                    item[
                        "type"
                    ],

                "price":
                    price,

                "change":
                    _to_float(
                        quote.get(
                            "change"
                        )
                    ),

                "changePercent":
                    _to_float(
                        quote.get(
                            "percent_change"
                        )
                    ),

                "previousClose":
                    _to_float(
                        quote.get(
                            "previous_close"
                        )
                    ),

                "currency":
                    quote.get(
                        "currency"
                    ),
            }


            results.append(
                result
            )


            # Update shared caches.

            if price is not None:

                _set_cached(
                    _price_cache,
                    symbol,
                    price,
                )


        _set_cached(
            _market_overview_cache,
            cache_key,
            results,
        )


        return results


    except Exception as e:

        print(
            "MARKET OVERVIEW ERROR:",
            e,
        )


        stale = _get_stale_cached(
            _market_overview_cache,
            cache_key,
        )


        if stale is not None:

            return stale


        # -------------------------------------------------
        # FINAL FALLBACK
        #
        # Return existing price-cache data rather than
        # triggering more API requests.
        # -------------------------------------------------

        for item in MARKET_OVERVIEW_SYMBOLS:

            symbol = item[
                "symbol"
            ]


            price = _get_stale_cached(
                _price_cache,
                symbol,
            )


            quote = _get_stale_cached(
                _quote_cache,
                symbol,
            )


            results.append({

                "symbol":
                    symbol,

                "name":
                    item[
                        "name"
                    ],

                "type":
                    item[
                        "type"
                    ],

                "price":
                    price,

                "change":
                    (
                        quote.get(
                            "change"
                        )
                        if quote
                        else None
                    ),

                "changePercent":
                    (
                        quote.get(
                            "changePercent"
                        )
                        if quote
                        else None
                    ),

                "previousClose":
                    (
                        quote.get(
                            "previousClose"
                        )
                        if quote
                        else None
                    ),

                "currency":
                    (
                        quote.get(
                            "currency"
                        )
                        if quote
                        else None
                    ),
            })


        return results


# =========================================================
# MARKET MOVERS
# =========================================================

MARKET_MOVER_SYMBOLS = [

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


def get_market_movers():

    cache_key = (
        "market_movers"
    )


    cached = _get_cached(
        _market_movers_cache,
        cache_key,
        MARKET_MOVERS_CACHE_SECONDS,
    )

    if cached is not None:

        return cached


    results = []


    try:

        symbols = ",".join(
            MARKET_MOVER_SYMBOLS
        )


        data = _get(
            "quote",
            {
                "symbol":
                    symbols,
            },
        )


        if isinstance(
            data,
            dict,
        ):

            for symbol in (
                MARKET_MOVER_SYMBOLS
            ):

                quote = data.get(
                    symbol
                )


                if not isinstance(
                    quote,
                    dict,
                ):

                    continue


                price = _to_float(
                    quote.get(
                        "close"
                    )
                )


                if price is None:

                    continue


                result = {

                    "symbol":
                        symbol,

                    "price":
                        price,

                    "change":
                        _to_float(
                            quote.get(
                                "change"
                            )
                        ),

                    "changePercent":
                        _to_float(
                            quote.get(
                                "percent_change"
                            )
                        ),

                    "currency":
                        quote.get(
                            "currency"
                        ),
                }


                results.append(
                    result
                )


                # Update shared caches.

                _set_cached(
                    _price_cache,
                    symbol,
                    price,
                )


                _set_cached(
                    _quote_cache,
                    symbol,
                    {
                        "symbol":
                            symbol,

                        "price":
                            price,

                        "change":
                            result[
                                "change"
                            ],

                        "changePercent":
                            result[
                                "changePercent"
                            ],

                        "currency":
                            result[
                                "currency"
                            ],
                    },
                )


        gainers = sorted(

            results,

            key=lambda item: (
                item[
                    "changePercent"
                ]
                if item[
                    "changePercent"
                ]
                is not None
                else -999999
            ),

            reverse=True,

        )[:5]


        losers = sorted(

            results,

            key=lambda item: (
                item[
                    "changePercent"
                ]
                if item[
                    "changePercent"
                ]
                is not None
                else 999999
            ),

        )[:5]


        response = {

            "gainers":
                gainers,

            "losers":
                losers,
        }


        _set_cached(
            _market_movers_cache,
            cache_key,
            response,
        )


        return response


    except Exception as e:

        print(
            "MARKET MOVERS ERROR:",
            e,
        )


        stale = _get_stale_cached(
            _market_movers_cache,
            cache_key,
        )


        if stale is not None:

            return stale


        return {

            "gainers": [],
            "losers": [],
        }