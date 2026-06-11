"""News embedding model for pgvector RAG pipeline."""

from datetime import datetime, timezone
from app.extensions import db
from pgvector.sqlalchemy import Vector


class NewsEmbedding(db.Model):
    """Stores vector embeddings for news article chunks."""

    __tablename__ = "news_embeddings"

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey("news_articles.id"), nullable=False, index=True)
    embedding = db.Column(Vector(1024), nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    ticker = db.Column(db.String(20), index=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<NewsEmbedding news_id={self.news_id}>"
