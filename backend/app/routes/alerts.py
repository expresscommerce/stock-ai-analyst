"""Price alerts API routes."""

import logging
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.alert import PriceAlert

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """Get all active alerts."""
    alerts = PriceAlert.query.filter_by(is_active=True).order_by(
        PriceAlert.created_at.desc()
    ).all()
    return jsonify({"alerts": [a.to_dict() for a in alerts]})


@alerts_bp.route("/alerts", methods=["POST"])
def create_alert():
    """Create a new price alert."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["ticker", "alert_type", "threshold_value"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    valid_types = ["price_above", "price_below", "volume_spike"]
    if data["alert_type"] not in valid_types:
        return jsonify({"error": f"Invalid alert_type. Must be one of: {valid_types}"}), 400

    alert = PriceAlert(
        ticker=data["ticker"].upper(),
        alert_type=data["alert_type"],
        threshold_value=float(data["threshold_value"]),
    )
    db.session.add(alert)
    db.session.commit()

    return jsonify({"alert": alert.to_dict()}), 201


@alerts_bp.route("/alerts/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    """Delete (deactivate) an alert."""
    alert = PriceAlert.query.get_or_404(alert_id)
    alert.is_active = False
    db.session.commit()
    return jsonify({"message": "Alert deactivated", "id": alert_id})


@alerts_bp.route("/alerts/check", methods=["POST"])
def check_alerts():
    """Check all active alerts against current prices."""
    from app.services.stock_fetcher import fetch_single_ticker
    from datetime import datetime, timezone

    active_alerts = PriceAlert.query.filter_by(is_active=True).all()
    triggered = []

    for alert in active_alerts:
        data = fetch_single_ticker(alert.ticker)
        if not data:
            continue

        price = data.get("price", 0)
        volume = data.get("volume", 0)

        should_trigger = False
        if alert.alert_type == "price_above" and price >= alert.threshold_value:
            should_trigger = True
        elif alert.alert_type == "price_below" and price <= alert.threshold_value:
            should_trigger = True
        elif alert.alert_type == "volume_spike" and volume >= alert.threshold_value:
            should_trigger = True

        if should_trigger:
            alert.is_active = False
            alert.triggered_at = datetime.now(timezone.utc)
            triggered.append({
                "alert": alert.to_dict(),
                "current_price": price,
                "current_volume": volume,
            })

    db.session.commit()
    return jsonify({"triggered": triggered})
