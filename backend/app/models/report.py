"""Daily AI-generated market report model."""

from datetime import datetime, timezone
from app.extensions import db


class DailyReport(db.Model):
    """Stores AI-generated daily market briefings."""

    __tablename__ = "daily_reports"

    id = db.Column(db.Integer, primary_key=True)
    report_date = db.Column(db.Date, unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    market_summary = db.Column(db.Text)
    top_movers = db.Column(db.JSON)
    sector_performance = db.Column(db.JSON)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "content": self.content,
            "market_summary": self.market_summary,
            "top_movers": self.top_movers,
            "sector_performance": self.sector_performance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DailyReport {self.report_date}>"
