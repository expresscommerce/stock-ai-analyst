"""Stock price database model."""

from datetime import datetime, timezone
from app.extensions import db


class StockPrice(db.Model):
    """Stores historical and current stock price data."""

    __tablename__ = "stock_prices"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False, index=True)
    company_name = db.Column(db.String(200))
    price = db.Column(db.Float)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    market_cap = db.Column(db.BigInteger)
    pe_ratio = db.Column(db.Float)
    week_52_high = db.Column(db.Float)
    week_52_low = db.Column(db.Float)
    dividend_yield = db.Column(db.Float)
    percent_change = db.Column(db.Float)
    exchange = db.Column(db.String(50))
    currency = db.Column(db.String(10), default="USD")
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "price": self.price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "week_52_high": self.week_52_high,
            "week_52_low": self.week_52_low,
            "dividend_yield": self.dividend_yield,
            "percent_change": self.percent_change,
            "exchange": self.exchange,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f"<StockPrice {self.ticker} @ {self.price}>"
