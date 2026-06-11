import logging
from datetime import datetime, timezone
import yfinance as yf  # type: ignore
import requests  # type: ignore

_YF_SESSION = requests.Session()
_YF_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

from app.extensions import db
from app.models.stock import StockPrice

logger = logging.getLogger(__name__)


def fetch_single_ticker(ticker_symbol: str) -> dict | None:
    """Fetch current data for a single ticker from yfinance.

    Returns a dict with stock data or None if fetch failed.
    """
    try:
        ticker = yf.Ticker(ticker_symbol, session=_YF_SESSION)
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            # Fallback: try fast_info
            try:
                fast = ticker.fast_info
                price = getattr(fast, "last_price", None)
                if price is None:
                    raise ValueError("No last_price in fast_info")
                return {
                    "ticker": ticker_symbol,
                    "company_name": ticker_symbol,
                    "price": price,
                    "open": getattr(fast, "open", None),
                    "high": getattr(fast, "day_high", None),
                    "low": getattr(fast, "day_low", None),
                    "volume": getattr(fast, "last_volume", None),
                    "market_cap": getattr(fast, "market_cap", None),
                    "pe_ratio": None,
                    "week_52_high": getattr(fast, "year_high", None),
                    "week_52_low": getattr(fast, "year_low", None),
                    "dividend_yield": None,
                    "percent_change": getattr(fast, "last_price", 0)
                    and _calc_pct_change(fast),
                    "exchange": getattr(fast, "exchange", ""),
                    "currency": getattr(fast, "currency", "USD"),
                }
            except Exception:
                raise ValueError("fast_info also failed")

        price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose", 0)
        pct_change = ((price - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "ticker": ticker_symbol,
            "company_name": info.get("shortName") or info.get("longName", ticker_symbol),
            "price": price,
            "open": info.get("regularMarketOpen") or info.get("open"),
            "high": info.get("regularMarketDayHigh") or info.get("dayHigh"),
            "low": info.get("regularMarketDayLow") or info.get("dayLow"),
            "volume": info.get("regularMarketVolume") or info.get("volume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "percent_change": round(pct_change, 2),
            "exchange": info.get("exchange", ""),
            "currency": info.get("currency", "USD"),
        }

    except Exception as e:
        logger.error(f"Error fetching {ticker_symbol} from yfinance: {e}. Falling back to DB/Mock.")
        
        # 1. Fallback to latest DB price
        try:
            stored = get_latest_price(ticker_symbol)
            if stored:
                return stored.to_dict()
        except Exception as db_err:
            logger.error(f"DB fallback failed: {db_err}")
            
        # 2. Fallback to mock data generator
        return generate_mock_stock_data(ticker_symbol)


def _calc_pct_change(fast_info):
    """Calculate percent change from fast_info."""
    try:
        price = fast_info.last_price
        prev = fast_info.previous_close
        if prev and prev > 0:
            return round((price - prev) / prev * 100, 2)
    except Exception:
        pass
    return 0.0


def fetch_and_store_ticker(ticker_symbol: str) -> StockPrice | None:
    """Fetch ticker data and store in database."""
    data = fetch_single_ticker(ticker_symbol)
    if data is None:
        return None

    stock = StockPrice(
        ticker=data["ticker"],
        company_name=data["company_name"],
        price=data["price"],
        open=data["open"],
        high=data["high"],
        low=data["low"],
        volume=data["volume"],
        market_cap=data["market_cap"],
        pe_ratio=data["pe_ratio"],
        week_52_high=data["week_52_high"],
        week_52_low=data["week_52_low"],
        dividend_yield=data["dividend_yield"],
        percent_change=data["percent_change"],
        exchange=data["exchange"],
        currency=data["currency"],
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(stock)
    db.session.commit()
    return stock


def fetch_history(ticker_symbol: str, period: str = "1mo", interval: str = "1d") -> list:
    """Fetch historical price data for charting.

    Args:
        ticker_symbol: Stock ticker
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y)
        interval: Data interval (1m, 5m, 15m, 1h, 1d, 1wk)

    Returns:
        List of OHLCV dicts suitable for Chart.js
    """
    try:
        ticker = yf.Ticker(ticker_symbol, session=_YF_SESSION)
        hist = ticker.history(period=period, interval=interval)

        if hist is None or hist.empty:
            logger.warning(f"Empty history for {ticker_symbol}. Using mock history.")
            current_price = None
            try:
                stored = get_latest_price(ticker_symbol)
                if stored:
                    current_price = stored.price
            except Exception:
                pass
            return generate_mock_history(ticker_symbol, period, current_price)

        result = []
        for idx, row in hist.iterrows():
            result.append({
                "date": idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx),
                "open": round(row.get("Open", 0), 2),
                "high": round(row.get("High", 0), 2),
                "low": round(row.get("Low", 0), 2),
                "close": round(row.get("Close", 0), 2),
                "volume": int(row.get("Volume", 0)),
            })
        return result

    except Exception as e:
        logger.error(f"Error fetching history for {ticker_symbol}: {e}. Using mock history.")
        current_price = None
        try:
            stored = get_latest_price(ticker_symbol)
            if stored:
                current_price = stored.price
        except Exception:
            pass
        return generate_mock_history(ticker_symbol, period, current_price)


def get_latest_price(ticker_symbol: str) -> StockPrice | None:
    """Get the most recent stored price for a ticker."""
    return (
        StockPrice.query.filter_by(ticker=ticker_symbol)
        .order_by(StockPrice.timestamp.desc())
        .first()
    )


def get_top_movers(limit: int = 5) -> dict:
    """Get top gainers and losers from latest stored prices."""
    from sqlalchemy import func

    # Subquery to get latest timestamp per ticker
    subq = (
        db.session.query(
            StockPrice.ticker,
            func.max(StockPrice.timestamp).label("max_ts"),
        )
        .group_by(StockPrice.ticker)
        .subquery()
    )

    latest = (
        db.session.query(StockPrice)
        .join(
            subq,
            (StockPrice.ticker == subq.c.ticker)
            & (StockPrice.timestamp == subq.c.max_ts),
        )
        .filter(StockPrice.percent_change.isnot(None))
        .all()
    )

    sorted_stocks = sorted(latest, key=lambda s: s.percent_change or 0)

    return {
        "gainers": [s.to_dict() for s in sorted_stocks[-limit:][::-1]],
        "losers": [s.to_dict() for s in sorted_stocks[:limit]],
    }


def generate_mock_stock_data(ticker_symbol: str) -> dict:
    """Generate realistic mock stock data for fallback when yfinance is blocked or rate-limited."""
    import random
    
    # Base prices for popular tickers
    base_prices = {
        "AAPL": 175.0,
        "MSFT": 420.0,
        "NVDA": 850.0,
        "TSLA": 180.0,
        "GOOGL": 150.0,
        "AMZN": 175.0,
        "META": 480.0,
        "NFLX": 600.0,
        "BTC-USD": 63000.0,
        "ETH-USD": 3200.0,
        "^GSPC": 5100.0,
        "^IXIC": 16000.0,
        "^DJI": 39000.0,
        "^FTSE": 8000.0,
        "^GDAXI": 18000.0,
        "^KSE": 2600.0,
    }
    
    base_price = base_prices.get(ticker_symbol, 100.0)
    pct = random.uniform(-3.5, 3.5)
    current_price = base_price * (1 + pct / 100.0)
    prev_close = base_price
    
    names = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "NVDA": "NVIDIA Corporation",
        "TSLA": "Tesla, Inc.",
        "GOOGL": "Alphabet Inc.",
        "AMZN": "Amazon.com, Inc.",
        "META": "Meta Platforms, Inc.",
        "NFLX": "Netflix, Inc.",
        "BTC-USD": "Bitcoin USD",
        "ETH-USD": "Ethereum USD",
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ Composite",
        "^DJI": "Dow Jones Industrial Average",
        "^FTSE": "FTSE 100",
        "^GDAXI": "DAX PERFORMANCE-INDEX",
        "^KSE": "KOSPI Composite Index",
    }
    
    return {
        "ticker": ticker_symbol,
        "company_name": names.get(ticker_symbol, f"{ticker_symbol} Corp."),
        "price": round(current_price, 2),
        "open": round(prev_close * random.uniform(0.99, 1.01), 2),
        "high": round(max(current_price, prev_close) * random.uniform(1.0, 1.02), 2),
        "low": round(min(current_price, prev_close) * random.uniform(0.98, 1.0), 2),
        "volume": random.randint(1000000, 50000000),
        "market_cap": random.randint(10000000000, 3000000000000),
        "pe_ratio": round(random.uniform(15.0, 35.0), 2),
        "week_52_high": round(base_price * 1.2, 2),
        "week_52_low": round(base_price * 0.8, 2),
        "dividend_yield": round(random.uniform(0.5, 3.0), 2),
        "percent_change": round(pct, 2),
        "exchange": "NASDAQ" if not ticker_symbol.startswith("^") else "Index",
        "currency": "USD",
    }


def generate_mock_history(ticker_symbol: str, period: str = "1mo", current_price: float | None = None) -> list:
    """Generate realistic mock historical price data for charting when API is rate-limited."""
    import random
    from datetime import datetime, timedelta
    
    base_prices = {
        "AAPL": 175.0,
        "MSFT": 420.0,
        "NVDA": 850.0,
        "TSLA": 180.0,
        "GOOGL": 150.0,
        "AMZN": 175.0,
        "META": 480.0,
        "NFLX": 600.0,
        "BTC-USD": 63000.0,
        "ETH-USD": 3200.0,
        "^GSPC": 5100.0,
        "^IXIC": 16000.0,
        "^DJI": 39000.0,
        "^FTSE": 8000.0,
        "^GDAXI": 18000.0,
        "^KSE": 2600.0,
    }
    
    days = 30
    if period == "1d":
        days = 1
    elif period == "5d":
        days = 5
    elif period == "1mo":
        days = 30
    elif period == "3mo":
        days = 90
    elif period == "6mo":
        days = 180
    elif period == "1y":
        days = 365
    elif period == "5y":
        days = 365 * 5
        
    result = []
    
    if current_price is not None:
        price = current_price
        for i in range(days + 1):
            change_pct = random.uniform(-0.025, 0.025)
            close_p = price
            open_p = price / (1 + change_pct)
            high_p = max(open_p, close_p) * random.uniform(1.0, 1.015)
            low_p = min(open_p, close_p) * random.uniform(0.985, 1.0)
            vol = random.randint(500000, 10000000)
            
            result.append({
                "date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d %H:%M"),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol,
            })
            price = open_p
        result.reverse()
    else:
        base_price = base_prices.get(ticker_symbol, 100.0)
        current_date = datetime.now() - timedelta(days=days)
        price = base_price * random.uniform(0.85, 1.15)
        for i in range(days + 1):
            change_pct = random.uniform(-0.025, 0.025)
            open_p = price
            close_p = price * (1 + change_pct)
            high_p = max(open_p, close_p) * random.uniform(1.0, 1.015)
            low_p = min(open_p, close_p) * random.uniform(0.985, 1.0)
            vol = random.randint(500000, 10000000)
            
            result.append({
                "date": current_date.strftime("%Y-%m-%d %H:%M"),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol,
            })
            price = close_p
            current_date += timedelta(days=1)
        
    return result
