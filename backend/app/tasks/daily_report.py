"""Celery task: Generate daily market report at 9 AM UTC."""

import logging
from datetime import date
from app.extensions import celery, db

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.daily_report.run")
def run():
    """Generate a comprehensive daily market briefing using AI."""
    from flask import current_app
    from app.services.stock_fetcher import fetch_single_ticker
    from app.services.ai_analyst import _get_client
    from app.models.report import DailyReport

    today = date.today()

    # Check if report already exists for today
    existing = DailyReport.query.filter_by(report_date=today).first()
    if existing:
        logger.info(f"Daily report already exists for {today}")
        return {"status": "exists", "date": str(today)}

    # Gather market data
    config = current_app.config
    market_data = []

    # Fetch indices
    for idx in config["DEFAULT_INDICES"]:
        data = fetch_single_ticker(idx)
        if data:
            market_data.append(
                f"{data['company_name']} ({idx}): ${data['price']:.2f} ({data['percent_change']:+.2f}%)"
            )

    # Fetch top stocks
    top_movers = []
    for ticker in config["DEFAULT_TICKERS"][:10]:
        data = fetch_single_ticker(ticker)
        if data:
            top_movers.append({
                "ticker": ticker,
                "name": data.get("company_name", ticker),
                "price": data.get("price"),
                "change": data.get("percent_change", 0),
            })

    sorted_movers = sorted(top_movers, key=lambda x: x["change"])
    top_gainers = sorted_movers[-3:][::-1]
    top_losers = sorted_movers[:3]

    movers_text = "Top Gainers:\n"
    for m in top_gainers:
        movers_text += f"  {m['ticker']} ({m['name']}): ${m['price']:.2f} ({m['change']:+.2f}%)\n"
    movers_text += "Top Losers:\n"
    for m in top_losers:
        movers_text += f"  {m['ticker']} ({m['name']}): ${m['price']:.2f} ({m['change']:+.2f}%)\n"

    # Get sector performance
    sector_etfs = {
        "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
        "Energy": "XLE", "Consumer Disc.": "XLY",
    }
    sector_perf = {}
    for sector, etf in sector_etfs.items():
        data = fetch_single_ticker(etf)
        if data:
            sector_perf[sector] = data.get("percent_change", 0)

    sector_text = "Sector Performance:\n"
    for sector, change in sector_perf.items():
        sector_text += f"  {sector}: {change:+.2f}%\n"

    # Build prompt
    prompt = f"""Generate a comprehensive morning market briefing for {today.strftime('%B %d, %Y')}.

Market Overview:
{chr(10).join(market_data)}

{movers_text}
{sector_text}

Please provide:
1. A 2-3 sentence market summary
2. Key themes and trends to watch
3. Notable movers analysis
4. Sector highlights
5. What to watch today

Keep it professional, concise, and insightful. Around 300-400 words."""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=config["DEEPINFRA_CHAT_MODEL"],
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional financial market analyst writing a daily morning briefing for traders and investors.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.7,
        )

        report_content = response.choices[0].message.content

        # Create brief market summary (first paragraph)
        summary_lines = report_content.split("\n")
        market_summary = summary_lines[0] if summary_lines else "Market briefing generated."

        report = DailyReport(
            report_date=today,
            content=report_content,
            market_summary=market_summary,
            top_movers={
                "gainers": top_gainers,
                "losers": top_losers,
            },
            sector_performance=sector_perf,
        )
        db.session.add(report)
        db.session.commit()

        logger.info(f"Daily report generated for {today}")
        return {"status": "created", "date": str(today)}

    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        return {"status": "error", "message": str(e)}
