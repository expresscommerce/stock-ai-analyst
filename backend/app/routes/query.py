"""Natural language query API endpoint."""

import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context

from app.services.ai_analyst import detect_tickers, answer_query, stream_answer
from app.services.stock_fetcher import fetch_single_ticker
from app.services.technical import get_indicator_summary
from app.services.rag_pipeline import build_context

logger = logging.getLogger(__name__)

query_bp = Blueprint("query", __name__)


@query_bp.route("/query", methods=["POST"])
def process_query():
    """Process a natural language query about stocks.

    Detects tickers, builds context from stock data + RAG, and returns AI answer.
    """
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    stream = data.get("stream", False)

    # Step 1: Detect tickers in the question
    tickers = detect_tickers(question)
    logger.info(f"Query: '{question}' | Detected tickers: {tickers}")

    # Step 2: Fetch stock data for detected tickers
    context_parts = []
    for ticker in tickers[:3]:  # Limit to 3 tickers
        stock_data = fetch_single_ticker(ticker)
        if stock_data:
            context_parts.append(f"\n[STOCK DATA] {ticker}:")
            for k, v in stock_data.items():
                if v is not None:
                    context_parts.append(f"  {k}: {v}")

            # Add technical summary
            tech_summary = get_indicator_summary(ticker)
            context_parts.append(f"\n[TECHNICAL] {ticker}:")
            context_parts.append(tech_summary)

    # Step 3: RAG search for relevant news
    primary_ticker = tickers[0] if tickers else None
    rag_context = build_context(question, ticker=primary_ticker)
    if rag_context:
        context_parts.append(rag_context)

    full_context = "\n".join(context_parts)

    # Step 4: Get AI answer
    if stream:
        def generate():
            for chunk in stream_answer(question, full_context):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    answer = answer_query(question, full_context)

    return jsonify({
        "answer": answer,
        "tickers": tickers,
    })
