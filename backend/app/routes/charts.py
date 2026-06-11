"""Chart data API routes."""

import logging
from flask import Blueprint, jsonify, request

from app.services.stock_fetcher import fetch_history
from app.services.technical import get_technical_indicators
from app.extensions import limiter

logger = logging.getLogger(__name__)

charts_bp = Blueprint("charts", __name__)


@charts_bp.route("/charts/history")
@limiter.limit("30 per minute")
def chart_history():
    """Get historical data for multiple tickers (for heatmap/comparison)."""
    tickers = request.args.get("tickers", "").split(",")
    period = request.args.get("period", "1mo")

    if not tickers or tickers == [""]:
        return jsonify({"error": "No tickers specified"}), 400

    result = {}
    for ticker in tickers[:20]:  # Limit to 20
        ticker = ticker.strip().upper()
        if ticker:
            result[ticker] = fetch_history(ticker, period=period)

    return jsonify(result)


@charts_bp.route("/charts/sector-heatmap")
@limiter.limit("10 per minute")
def sector_heatmap():
    """Get sector performance data for heatmap visualization."""
    # Sector ETFs as proxies
    sector_etfs = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Disc.": "XLY",
        "Communication": "XLC",
        "Industrials": "XLI",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Materials": "XLB",
    }

    from app.services.stock_fetcher import fetch_single_ticker

    sectors = []
    for sector_name, etf in sector_etfs.items():
        data = fetch_single_ticker(etf)
        if data:
            sectors.append({
                "name": sector_name,
                "etf": etf,
                "price": data.get("price"),
                "percent_change": data.get("percent_change", 0),
            })

    return jsonify({"sectors": sectors})


@charts_bp.route("/charts/technical/<ticker>")
@limiter.limit("30 per minute")
def chart_technical(ticker):
    """Get technical indicator data for chart overlays."""
    ticker = ticker.upper()
    indicators = get_technical_indicators(ticker, period="6mo")
    return jsonify(indicators)
