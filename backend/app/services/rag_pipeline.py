"""RAG pipeline using DeepInfra BGE-M3 embeddings and pgvector."""

import logging
from openai import OpenAI
from flask import current_app

from app.extensions import db
from app.models.embedding import NewsEmbedding
from app.models.news import NewsArticle

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    """Get DeepInfra OpenAI-compatible client."""
    return OpenAI(
        api_key=current_app.config["DEEPINFRA_API_KEY"],
        base_url=current_app.config["DEEPINFRA_BASE_URL"],
    )


def generate_embedding(text: str) -> list[float] | None:
    """Generate a 1024-dim embedding using BGE-M3.

    Args:
        text: Text to embed

    Returns:
        List of 1024 floats or None on failure.
    """
    try:
        client = _get_client()
        response = client.embeddings.create(
            model=current_app.config["DEEPINFRA_EMBEDDING_MODEL"],
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by approximate token count.

    Uses word-based splitting (~0.75 words per token estimate).
    """
    if not text:
        return []

    words = text.split()
    # Approximate: 1 token ≈ 0.75 words, so chunk_size tokens ≈ chunk_size * 0.75 words
    word_chunk = int(chunk_size * 0.75)
    word_overlap = int(overlap * 0.75)

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + word_chunk, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += word_chunk - word_overlap

    return chunks


def embed_article(article: NewsArticle) -> int:
    """Generate embeddings for a news article and store in pgvector.

    Args:
        article: NewsArticle instance to embed

    Returns:
        Number of chunks embedded.
    """
    # Combine title + description + content
    full_text = " ".join(filter(None, [
        article.title,
        article.description,
        article.content,
    ]))

    chunks = chunk_text(full_text)
    embedded_count = 0

    for chunk in chunks:
        embedding = generate_embedding(chunk)
        if embedding is None:
            continue

        # Determine primary ticker for this article
        ticker = article.tickers[0] if article.tickers else None

        emb = NewsEmbedding(
            news_id=article.id,
            embedding=embedding,
            chunk_text=chunk,
            ticker=ticker,
        )
        db.session.add(emb)
        embedded_count += 1

    if embedded_count > 0:
        db.session.commit()
        logger.info(f"Embedded {embedded_count} chunks for article {article.id}")

    return embedded_count


def similarity_search(query: str, top_k: int = 5, ticker: str | None = None) -> list[dict]:
    """Search for similar news chunks using cosine similarity.

    Args:
        query: Search query text
        top_k: Number of results to return
        ticker: Optional ticker to filter results

    Returns:
        List of dicts with chunk_text, similarity score, and metadata.
    """
    query_embedding = generate_embedding(query)
    if query_embedding is None:
        return []

    try:
        # Build the query using pgvector cosine distance
        base_query = db.session.query(
            NewsEmbedding,
            NewsEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
        )

        if ticker:
            base_query = base_query.filter(NewsEmbedding.ticker == ticker)

        results = (
            base_query
            .order_by("distance")
            .limit(top_k)
            .all()
        )

        return [
            {
                "chunk_text": emb.chunk_text,
                "similarity": round(1 - distance, 4),  # Convert distance to similarity
                "ticker": emb.ticker,
                "news_id": emb.news_id,
            }
            for emb, distance in results
        ]
    except Exception as e:
        logger.error(f"Similarity search error: {e}")
        return []


def build_context(question: str, stock_data: dict | None = None, ticker: str | None = None) -> str:
    """Build full context for AI query from stock data + RAG results.

    Args:
        question: User's question
        stock_data: Stock metrics dict
        ticker: Primary ticker symbol

    Returns:
        Formatted context string.
    """
    parts = []

    # Add stock data context
    if stock_data:
        parts.append("[STOCK DATA]:")
        for key, val in stock_data.items():
            if val is not None:
                parts.append(f"  {key}: {val}")

    # RAG: search for relevant news
    relevant_chunks = similarity_search(question, top_k=5, ticker=ticker)
    if relevant_chunks:
        parts.append("\n[NEWS CONTEXT]:")
        for i, chunk in enumerate(relevant_chunks, 1):
            parts.append(f"  {i}. (relevance: {chunk['similarity']}) {chunk['chunk_text']}")

    return "\n".join(parts)
