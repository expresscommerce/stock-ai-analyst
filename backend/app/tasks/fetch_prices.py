"""Celery task: Fetch stock prices every 5 minutes."""

import logging
from app.extensions import celery, socketio
from flask import current_app

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.fetch_prices.run")
def run():
    """Fetch prices for all tracked tickers and broadcast updates."""
    from app.services.stock_fetcher import fetch_and_store_ticker

    tickers = current_app.config["DEFAULT_TICKERS"] + current_app.config["DEFAULT_INDICES"]
    results = []

    for ticker in tickers:
        try:
            stock = fetch_and_store_ticker(ticker)
            if stock:
                results.append(stock.to_dict())
                logger.info(f"Fetched {ticker}: ${stock.price}")
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")

    # Broadcast updates via WebSocket
    if results:
        try:
            socketio.emit("price_update", {"stocks": results}, namespace="/")
        except Exception as e:
            logger.warning(f"WebSocket broadcast error: {e}")

    logger.info(f"Price fetch complete: {len(results)}/{len(tickers)} tickers updated")
    return {"updated": len(results), "total": len(tickers)}
