"""Celery task: Fetch and process news every hour."""

import logging
from app.extensions import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.fetch_news.run")
def run():
    """Fetch financial news, store, embed, and score sentiment."""
    from app.services.news_fetcher import fetch_general_news, store_articles
    from app.services.rag_pipeline import embed_article
    from app.services.ai_analyst import score_sentiment
    from app.models.news import NewsArticle
    from app.extensions import db

    # Step 1: Fetch general financial news
    articles = fetch_general_news(page_size=20)
    stored_count = store_articles(articles)
    logger.info(f"Stored {stored_count} new general articles")

    # Step 2: Fetch ticker-specific news for top tickers
    from flask import current_app
    from app.services.news_fetcher import fetch_ticker_news

    for ticker in current_app.config["DEFAULT_TICKERS"][:5]:
        try:
            ticker_articles = fetch_ticker_news(ticker, page_size=5)
            store_articles(ticker_articles, tickers=[ticker])
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")

    # Step 3: Embed recent unembedded articles
    unembedded = (
        NewsArticle.query
        .filter(~NewsArticle.embeddings.any())
        .order_by(NewsArticle.published_at.desc())
        .limit(20)
        .all()
    )

    embedded_count = 0
    for article in unembedded:
        try:
            count = embed_article(article)
            embedded_count += count
        except Exception as e:
            logger.error(f"Error embedding article {article.id}: {e}")

    logger.info(f"Embedded {embedded_count} chunks from {len(unembedded)} articles")

    # Step 4: Score sentiment for unscored articles
    unscored = (
        NewsArticle.query
        .filter(NewsArticle.sentiment_label == "neutral")
        .filter(NewsArticle.sentiment_score == 0.0)
        .order_by(NewsArticle.published_at.desc())
        .limit(10)
        .all()
    )

    for article in unscored:
        try:
            text = f"{article.title}. {article.description or ''}"
            sentiment = score_sentiment(text)
            article.sentiment_score = sentiment["score"]
            article.sentiment_label = sentiment["label"]
        except Exception as e:
            logger.error(f"Error scoring sentiment for article {article.id}: {e}")

    db.session.commit()
    logger.info(f"Scored sentiment for {len(unscored)} articles")

    return {
        "stored": stored_count,
        "embedded": embedded_count,
        "sentiment_scored": len(unscored),
    }
