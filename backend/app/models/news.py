"""News article database model."""

from datetime import datetime, timezone
from app.extensions import db


class NewsArticle(db.Model):
    """Stores financial news articles with sentiment analysis."""

    __tablename__ = "news_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    source = db.Column(db.String(200))
    published_at = db.Column(db.DateTime, index=True)
    tickers = db.Column(db.ARRAY(db.String(20)), default=[])
    sentiment_score = db.Column(db.Float, default=0.0)
    sentiment_label = db.Column(db.String(20), default="neutral")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to embeddings
    embeddings = db.relationship(
        "NewsEmbedding", backref="article", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tickers": self.tickers or [],
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
        }

    def __repr__(self):
        return f"<NewsArticle {self.title[:50]}>"
