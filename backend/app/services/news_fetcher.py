"""NewsAPI integration for financial news fetching."""

import logging
from datetime import datetime, timezone
import requests  # type: ignore

from flask import current_app
from app.extensions import db
from app.models.news import NewsArticle

logger = logging.getLogger(__name__)

NEWS_API_BASE = "https://newsapi.org/v2"


def fetch_general_news(page_size: int = 20) -> list[dict]:
    """Fetch general financial news from NewsAPI.

    Returns list of article dicts.
    """
    api_key = current_app.config.get("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY not configured")
        return []

    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/everything",
            params={
                "q": "stock market OR finance OR economy OR Wall Street",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        logger.error(f"Error fetching general news: {e}")
        return []


def fetch_ticker_news(ticker: str, company_name: str = "", page_size: int = 10) -> list[dict]:
    """Fetch news related to a specific ticker.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        company_name: Full company name for better search
        page_size: Number of articles to fetch

    Returns list of article dicts.
    """
    api_key = current_app.config.get("NEWS_API_KEY")
    if not api_key:
        return []

    query = ticker
    if company_name:
        query = f"{ticker} OR {company_name}"

    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        return []


def store_articles(articles: list[dict], tickers: list[str] | None = None) -> int:
    """Store articles in database, skipping duplicates.

    Returns count of new articles stored.
    """
    stored = 0
    for article in articles:
        url = article.get("url")
        if not url:
            continue

        # Check for duplicate
        existing = NewsArticle.query.filter_by(url=url).first()
        if existing:
            continue

        # Parse published date
        pub_date = None
        pub_str = article.get("publishedAt")
        if pub_str:
            try:
                pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pub_date = datetime.now(timezone.utc)

        news = NewsArticle(
            title=article.get("title", ""),
            description=article.get("description", ""),
            content=article.get("content", ""),
            url=url,
            source=article.get("source", {}).get("name", "Unknown"),
            published_at=pub_date,
            tickers=tickers or [],
        )
        db.session.add(news)
        stored += 1

    if stored > 0:
        db.session.commit()
        logger.info(f"Stored {stored} new articles")

    return stored


def get_recent_news(limit: int = 20, ticker: str | None = None) -> list[dict]:
    """Get recent news from database.

    Args:
        limit: Maximum articles to return
        ticker: Optional ticker to filter by

    Returns list of article dicts.
    """
    query = NewsArticle.query.order_by(NewsArticle.published_at.desc())

    if ticker:
        query = query.filter(NewsArticle.tickers.any(ticker))

    articles = query.limit(limit).all()
    return [a.to_dict() for a in articles]
