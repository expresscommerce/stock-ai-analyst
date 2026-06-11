"""Price alert database model."""

from datetime import datetime, timezone
from app.extensions import db


class PriceAlert(db.Model):
    """Stores user-defined price alerts."""

    __tablename__ = "price_alerts"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False, index=True)
    alert_type = db.Column(
        db.String(30), nullable=False
    )  # price_above, price_below, volume_spike
    threshold_value = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    triggered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "threshold_value": self.threshold_value,
            "is_active": self.is_active,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<PriceAlert {self.ticker} {self.alert_type} @ {self.threshold_value}>"
