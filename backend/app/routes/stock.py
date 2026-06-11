"""Stock detail page routes."""

import logging
from flask import Blueprint, render_template, jsonify

from app.services.stock_fetcher import fetch_single_ticker, fetch_history
from app.services.news_fetcher import fetch_ticker_news, get_recent_news
from app.services.technical import get_technical_indicators, get_indicator_summary
from app.services.ai_analyst import analyze_stock
from app.services.rag_pipeline import similarity_search


logger = logging.getLogger(__name__)

stock_bp = Blueprint("stock", __name__)


@stock_bp.route("/stock/<ticker>")
def stock_detail(ticker):
    """Render stock detail page."""
    ticker = ticker.upper()
    return render_template("stock_detail.html", ticker=ticker)


@stock_bp.route("/api/stock/<ticker>/data")
def stock_data(ticker):
    """Get comprehensive stock data as JSON."""
    ticker = ticker.upper()

    # Fetch live data
    data = fetch_single_ticker(ticker)
    if not data:
        return jsonify({"error": f"Could not fetch data for {ticker}"}), 404

    # Technical indicators
    tech = get_technical_indicators(ticker)

    # Recent news for this ticker (fallback to live fetch if empty)
    news = get_recent_news(limit=5, ticker=ticker)
    if not news:
        try:
            from app.services.news_fetcher import fetch_ticker_news, store_articles
            live_news = fetch_ticker_news(ticker, page_size=5)
            if live_news:
                store_articles(live_news, tickers=[ticker])
                news = get_recent_news(limit=5, ticker=ticker)
        except Exception as e:
            logger.error(f"Error fetching live ticker news for {ticker}: {e}")

    res_data = {
        "stock": data,
        "technical": tech,
        "news": news,
    }
    return jsonify(res_data)


@stock_bp.route("/api/stock/<ticker>/history/<period>")
def stock_history(ticker, period):
    """Get historical price data for charting."""
    ticker = ticker.upper()

    # Map period to interval
    interval_map = {
        "1d": "5m",
        "5d": "15m",
        "1mo": "1d",
        "3mo": "1d",
        "6mo": "1d",
        "1y": "1wk",
        "5y": "1mo",
    }

    interval = interval_map.get(period, "1d")
    history = fetch_history(ticker, period=period, interval=interval)

    res_data = {"history": history, "period": period}
    return jsonify(res_data)


@stock_bp.route("/api/stock/<ticker>/analysis")
def stock_analysis(ticker):
    """Get AI-generated stock analysis."""
    ticker = ticker.upper()

    # Fetch current data
    data = fetch_single_ticker(ticker)
    if not data:
        return jsonify({"analysis": f"Unable to fetch data for {ticker}."})

    # Get technical summary
    tech_data = get_technical_indicators(ticker)
    tech_summary = get_indicator_summary(ticker)

    # Get relevant news via RAG
    news_chunks = similarity_search(f"Latest news about {ticker}", top_k=3, ticker=ticker)
    news_texts = [c["chunk_text"] for c in news_chunks] if news_chunks else []

    # Generate AI analysis
    analysis = analyze_stock(
        ticker=ticker,
        stock_data=data,
        news_context=news_texts,
        technical_data=tech_data,
    )

    return jsonify({"analysis": analysis, "ticker": ticker})
