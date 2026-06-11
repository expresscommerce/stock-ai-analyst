"""AI Analyst service using DeepInfra Llama 3.3 70B."""

import logging
import re
from openai import OpenAI  # type: ignore
from flask import current_app

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert financial analyst and stock market specialist with deep 
knowledge of global markets including NYSE, NASDAQ, LSE, and emerging markets.

You have access to real-time stock data and recent financial news provided 
to you as context. Your job is to:

1. Answer questions about stocks clearly and accurately
2. Base your analysis on the provided data and news context
3. Explain market movements in simple, understandable language
4. Highlight key risks and opportunities
5. Always mention that this is not financial advice

When analyzing stocks:
- Reference specific numbers from the provided data
- Mention relevant news that may have caused price movements  
- Explain technical indicators in plain English
- Be concise but thorough (aim for 150-250 words per response)
- Use bullet points for comparisons

Context will be provided in this format:
[STOCK DATA]: Current prices, % changes, volume, key metrics
[NEWS CONTEXT]: Recent relevant news articles
[TECHNICAL]: RSI, MACD, MA values

Always end with: "⚠️ This is not financial advice. Always do your own research."
"""


def _get_client() -> OpenAI:
    """Get DeepInfra OpenAI-compatible client."""
    return OpenAI(
        api_key=current_app.config["DEEPINFRA_API_KEY"],
        base_url=current_app.config["DEEPINFRA_BASE_URL"],
    )


def analyze_stock(ticker: str, stock_data: dict, news_context: list[str] | None = None,
                  technical_data: dict | None = None) -> str:
    """Generate AI analysis for a stock.

    Args:
        ticker: Stock ticker symbol
        stock_data: Current stock metrics dict
        news_context: List of relevant news text chunks
        technical_data: Technical indicator values

    Returns:
        AI-generated analysis text.
    """
    # Build context message
    context_parts = []

    context_parts.append(f"[STOCK DATA] for {ticker}:")
    for key, val in stock_data.items():
        if val is not None:
            context_parts.append(f"  {key}: {val}")

    if news_context:
        context_parts.append("\n[NEWS CONTEXT]:")
        for i, chunk in enumerate(news_context[:5], 1):
            context_parts.append(f"  {i}. {chunk[:500]}")

    if technical_data:
        context_parts.append("\n[TECHNICAL]:")
        for key, val in technical_data.items():
            context_parts.append(f"  {key}: {val}")

    context = "\n".join(context_parts)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=current_app.config["DEEPINFRA_CHAT_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Provide a concise analysis of {ticker} based on this data:\n\n{context}",
                },
            ],
            max_tokens=500,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response received from AI model")
        return content
    except Exception as e:
        logger.error(f"AI analysis error for {ticker}: {e}")
        return f"⚠️ AI analysis temporarily unavailable for {ticker}. Please try again later."


def answer_query(question: str, context: str = "") -> str:
    """Answer a natural language question about stocks.

    Args:
        question: User's question
        context: Pre-built context string with stock data + news

    Returns:
        AI-generated answer text.
    """
    user_message = question
    if context:
        user_message = f"Based on the following context, answer this question: {question}\n\nContext:\n{context}"

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=current_app.config["DEEPINFRA_CHAT_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=700,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response received from AI model")
        return content
    except Exception as e:
        logger.error(f"AI query error: {e}")
        return "⚠️ AI analysis is temporarily unavailable. Please try again later."


def stream_answer(question: str, context: str = ""):
    """Stream an answer using Server-Sent Events.

    Yields chunks of the response as they arrive.
    """
    user_message = question
    if context:
        user_message = f"Based on the following context, answer this question: {question}\n\nContext:\n{context}"

    try:
        client = _get_client()
        stream = client.chat.completions.create(
            model=current_app.config["DEEPINFRA_CHAT_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=700,
            temperature=0.7,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.error(f"AI stream error: {e}")
        yield "⚠️ AI analysis is temporarily unavailable. Please try again later."


def score_sentiment(text: str) -> dict:
    """Score the sentiment of a text using the AI model.

    Returns:
        Dict with 'score' (-1 to 1) and 'label' (positive/negative/neutral).
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=current_app.config["DEEPINFRA_CHAT_MODEL"],
            messages=[
                {
                    "role": "system",
                    "content": "You are a sentiment analysis tool. Respond with ONLY a JSON object: {\"score\": <float -1 to 1>, \"label\": \"<positive|negative|neutral>\"}. No other text.",
                },
                {
                    "role": "user",
                    "content": f"Analyze the financial sentiment of this text:\n\n{text[:1000]}",
                },
            ],
            max_tokens=50,
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response received from AI model")
        content = content.strip()
        # Parse JSON from response
        import json
        # Find JSON in response
        match = re.search(r'\{[^}]+\}', content)
        if match:
            result = json.loads(match.group())
            return {
                "score": float(result.get("score", 0)),
                "label": result.get("label", "neutral"),
            }
    except Exception as e:
        logger.error(f"Sentiment scoring error: {e}")

    return {"score": 0.0, "label": "neutral"}


def detect_tickers(text: str) -> list[str]:
    """Detect stock ticker symbols mentioned in text.

    Args:
        text: Input text to scan

    Returns:
        List of detected ticker symbols.
    """
    # Common ticker patterns: $AAPL, AAPL, etc.
    known_tickers = [
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "TSLA", "META",
        "BRK-B", "JPM", "JNJ", "QQQ", "SPY", "VTI", "BTC-USD", "ETH-USD",
        "GC=F", "CL=F", "SI=F", "NFLX", "AMD", "INTC", "DIS", "PYPL",
        "BA", "V", "MA", "WMT", "HD", "PG", "KO", "PEP", "COST", "ABBV",
        "MRK", "LLY", "UNH", "XOM", "CVX", "CRM", "ADBE", "ORCL",
    ]

    text_upper = text.upper()
    found = []

    # Check for $TICKER pattern
    dollar_tickers = re.findall(r'\$([A-Z]{1,5}(?:-[A-Z]+)?)', text_upper)
    found.extend(dollar_tickers)

    # Check for known tickers mentioned as standalone words
    for ticker in known_tickers:
        pattern = r'\b' + re.escape(ticker) + r'\b'
        if re.search(pattern, text_upper):
            if ticker not in found:
                found.append(ticker)

    # Also match common company names to tickers
    name_map = {
        "APPLE": "AAPL", "MICROSOFT": "MSFT", "GOOGLE": "GOOGL",
        "AMAZON": "AMZN", "NVIDIA": "NVDA", "TESLA": "TSLA",
        "FACEBOOK": "META", "NETFLIX": "NFLX", "BITCOIN": "BTC-USD",
        "ETHEREUM": "ETH-USD", "GOLD": "GC=F", "OIL": "CL=F",
        "SILVER": "SI=F",
    }
    for name, ticker in name_map.items():
        if name in text_upper and ticker not in found:
            found.append(ticker)

    return found
