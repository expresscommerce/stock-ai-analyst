"""Dashboard route - main page."""

import logging
from flask import Blueprint, render_template, jsonify, current_app

from app.services.stock_fetcher import fetch_single_ticker, get_top_movers, get_latest_price
from app.services.news_fetcher import get_recent_news
from app.services.currency import get_exchange_rates
from app.models.report import DailyReport

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Render the main dashboard page."""
    return render_template("dashboard.html")


@dashboard_bp.route("/api/dashboard-data")
def dashboard_data():
    """Get all dashboard data as JSON for frontend rendering."""
    config = current_app.config

    # Fetch global indices
    indices_data = []
    for idx_ticker in config["DEFAULT_INDICES"]:
        data = fetch_single_ticker(idx_ticker)
        if data:
            indices_data.append(data)

    # Fetch top movers from DB (or live if empty)
    movers = get_top_movers(limit=5)

    # If no DB data, fetch a few live tickers
    if not movers["gainers"] and not movers["losers"]:
        live_stocks = []
        for ticker in config["DEFAULT_TICKERS"][:10]:
            data = fetch_single_ticker(ticker)
            if data:
                live_stocks.append(data)

        sorted_live = sorted(live_stocks, key=lambda x: x.get("percent_change", 0))
        movers = {
            "gainers": sorted_live[-5:][::-1],
            "losers": sorted_live[:5],
        }

    # Recent news (fallback to live fetch if empty)
    news = get_recent_news(limit=10)
    if not news:
        try:
            from app.services.news_fetcher import fetch_general_news, store_articles
            live_news = fetch_general_news(page_size=10)
            if live_news:
                store_articles(live_news)
                news = get_recent_news(limit=10)
        except Exception as e:
            logger.error(f"Error fetching live general news: {e}")

    # Exchange rates
    rates = get_exchange_rates("USD")

    # Today's AI briefing
    from datetime import date
    daily_report = DailyReport.query.filter_by(report_date=date.today()).first()
    briefing = daily_report.to_dict() if daily_report else None

    return jsonify({
        "indices": indices_data,
        "movers": movers,
        "news": news,
        "exchange_rates": rates,
        "briefing": briefing,
    })
