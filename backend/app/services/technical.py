"""Technical indicators calculation using pandas-ta."""

import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests

_YF_SESSION = requests.Session()
_YF_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

logger = logging.getLogger(__name__)


def get_technical_indicators(ticker_symbol: str, period: str = "3mo") -> dict:
    """Calculate technical indicators for a stock.

    Args:
        ticker_symbol: Stock ticker
        period: Data period for calculation

    Returns:
        Dict with all indicator values and signals.
    """
    df = None
    try:
        ticker = yf.Ticker(ticker_symbol, session=_YF_SESSION)
        df = ticker.history(period=period, interval="1d")
    except Exception as e:
        logger.warning(f"Failed to fetch live technical history for {ticker_symbol}: {e}")

    try:

        if df is None or df.empty or len(df) < 20:
            logger.warning(f"Technical history empty for {ticker_symbol}. Using mock history dataframe.")
            from app.services.stock_fetcher import generate_mock_history
            mock_data = generate_mock_history(ticker_symbol, period)
            if mock_data:
                df = pd.DataFrame(mock_data)
                df = df.rename(columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                df.index = pd.to_datetime(df["date"])
            else:
                return _empty_indicators()

        result = {}

        # RSI (14-period)
        rsi = ta.rsi(df["Close"], length=14)
        if rsi is not None and not rsi.empty:
            current_rsi = round(rsi.iloc[-1], 2)
            result["rsi"] = current_rsi
            if current_rsi > 70:
                result["rsi_signal"] = "Overbought"
            elif current_rsi < 30:
                result["rsi_signal"] = "Oversold"
            else:
                result["rsi_signal"] = "Neutral"
        else:
            result["rsi"] = None
            result["rsi_signal"] = "N/A"

        # MACD
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            macd_cols = macd_df.columns.tolist()
            result["macd"] = round(macd_df[macd_cols[0]].iloc[-1], 4)
            result["macd_signal"] = round(macd_df[macd_cols[1]].iloc[-1], 4)
            result["macd_histogram"] = round(macd_df[macd_cols[2]].iloc[-1], 4)

            if result["macd"] > result["macd_signal"]:
                result["macd_trend"] = "Bullish"
            else:
                result["macd_trend"] = "Bearish"
        else:
            result["macd"] = None
            result["macd_signal"] = None
            result["macd_histogram"] = None
            result["macd_trend"] = "N/A"

        # Bollinger Bands
        bbands = getattr(ta, "bbands")(df["Close"], length=20, std=2)  # type: ignore
        if bbands is not None and not bbands.empty:
            bb_cols = bbands.columns.tolist()
            result["bb_lower"] = round(bbands[bb_cols[0]].iloc[-1], 2)
            result["bb_middle"] = round(bbands[bb_cols[1]].iloc[-1], 2)
            result["bb_upper"] = round(bbands[bb_cols[2]].iloc[-1], 2)

            current_price = df["Close"].iloc[-1]
            if current_price > result["bb_upper"]:
                result["bb_signal"] = "Above upper band (potential reversal)"
            elif current_price < result["bb_lower"]:
                result["bb_signal"] = "Below lower band (potential bounce)"
            else:
                result["bb_signal"] = "Within bands"
        else:
            result["bb_lower"] = None
            result["bb_middle"] = None
            result["bb_upper"] = None
            result["bb_signal"] = "N/A"

        # Simple Moving Averages
        sma_50 = ta.sma(df["Close"], length=50)
        sma_200 = ta.sma(df["Close"], length=200)

        result["sma_50"] = round(sma_50.iloc[-1], 2) if sma_50 is not None and not sma_50.empty else None
        result["sma_200"] = round(sma_200.iloc[-1], 2) if sma_200 is not None and not sma_200.empty else None

        # Golden Cross / Death Cross detection
        if result["sma_50"] and result["sma_200"]:
            if result["sma_50"] > result["sma_200"]:
                result["ma_cross"] = "Golden Cross (Bullish)"
            else:
                result["ma_cross"] = "Death Cross (Bearish)"

            # Check if cross just happened (within last 5 days)
            if sma_50 is not None and sma_200 is not None and len(sma_50) >= 5 and len(sma_200) >= 5:
                recent_50 = sma_50.iloc[-5:]
                recent_200 = sma_200.iloc[-5:]
                diff = recent_50 - recent_200
                if diff.iloc[0] * diff.iloc[-1] < 0:  # Sign change
                    result["ma_cross_recent"] = True
                else:
                    result["ma_cross_recent"] = False
        else:
            result["ma_cross"] = "Insufficient data"
            result["ma_cross_recent"] = False

        # Volume analysis
        avg_volume = df["Volume"].rolling(20).mean().iloc[-1]
        current_volume = df["Volume"].iloc[-1]
        result["avg_volume_20d"] = int(avg_volume) if pd.notna(avg_volume) else None
        result["current_volume"] = int(current_volume) if pd.notna(current_volume) else None

        if avg_volume and avg_volume > 0:
            volume_ratio = current_volume / avg_volume
            result["volume_ratio"] = round(volume_ratio, 2)
            result["volume_spike"] = volume_ratio > 2.0
        else:
            result["volume_ratio"] = None
            result["volume_spike"] = False

        # Current price for reference
        result["current_price"] = round(df["Close"].iloc[-1], 2)

        # Convert numpy/pandas datatypes to native python types for JSON serialization
        clean_result = {}
        for k, v in result.items():
            if v is None:
                clean_result[k] = None
            elif hasattr(v, "item"):
                clean_result[k] = v.item()
            elif isinstance(v, (bool, int, float, str)):
                clean_result[k] = v
            else:
                try:
                    clean_result[k] = float(v)
                except Exception:
                    clean_result[k] = str(v)
        return clean_result

    except Exception as e:
        logger.error(f"Technical analysis error for {ticker_symbol}: {e}")
        return _empty_indicators()


def _empty_indicators() -> dict:
    """Return empty indicator values."""
    return {
        "rsi": None, "rsi_signal": "N/A",
        "macd": None, "macd_signal": None, "macd_histogram": None, "macd_trend": "N/A",
        "bb_lower": None, "bb_middle": None, "bb_upper": None, "bb_signal": "N/A",
        "sma_50": None, "sma_200": None,
        "ma_cross": "N/A", "ma_cross_recent": False,
        "avg_volume_20d": None, "current_volume": None,
        "volume_ratio": None, "volume_spike": False,
        "current_price": None,
    }


def get_indicator_summary(ticker_symbol: str) -> str:
    """Get a text summary of technical indicators for AI context."""
    indicators = get_technical_indicators(ticker_symbol)

    lines = [f"Technical Analysis for {ticker_symbol}:"]

    if indicators["rsi"] is not None:
        lines.append(f"  RSI(14): {indicators['rsi']} - {indicators['rsi_signal']}")

    if indicators["macd"] is not None:
        lines.append(
            f"  MACD: {indicators['macd']}, Signal: {indicators['macd_signal']}, "
            f"Histogram: {indicators['macd_histogram']} - {indicators['macd_trend']}"
        )

    if indicators["sma_50"] is not None:
        lines.append(f"  SMA(50): {indicators['sma_50']}")

    if indicators["sma_200"] is not None:
        lines.append(f"  SMA(200): {indicators['sma_200']}")

    if indicators["ma_cross"] != "N/A":
        lines.append(f"  MA Cross: {indicators['ma_cross']}")

    if indicators["bb_signal"] != "N/A":
        lines.append(
            f"  Bollinger Bands: Lower={indicators['bb_lower']}, "
            f"Mid={indicators['bb_middle']}, Upper={indicators['bb_upper']} - {indicators['bb_signal']}"
        )

    if indicators["volume_spike"]:
        lines.append(
            f"  ⚠️ Volume Spike Detected! Current: {indicators['current_volume']:,}, "
            f"Avg: {indicators['avg_volume_20d']:,} (Ratio: {indicators['volume_ratio']}x)"
        )

    return "\n".join(lines)
