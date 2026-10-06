"""Forecasts, anomalies, model runs, alerts, tariffs and system settings."""
from app.extensions import db
from app.models.user import utcnow

SEVERITIES = ("NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL")


class Forecast(db.Model):
    __tablename__ = "forecasts"
    __table_args__ = (db.Index("ix_forecast_household_ts", "household_id", "forecast_timestamp"),)

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(
        db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    forecast_timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    predicted_kwh = db.Column(db.Float, nullable=False)
    lower_bound = db.Column(db.Float)
    upper_bound = db.Column(db.Float)
    model_name = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "forecast_timestamp": self.forecast_timestamp.isoformat(),
            "predicted_kwh": self.predicted_kwh,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "model_name": self.model_name,
        }


class Anomaly(db.Model):
    __tablename__ = "anomalies"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(
        db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consumption_record_id = db.Column(
        db.Integer, db.ForeignKey("consumption_records.id", ondelete="CASCADE"), nullable=False
    )
    expected_kwh = db.Column(db.Float, nullable=False)
    actual_kwh = db.Column(db.Float, nullable=False)
    difference_kwh = db.Column(db.Float, nullable=False)
    percentage_difference = db.Column(db.Float, nullable=False)
    anomaly_score = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(10), nullable=False, index=True)
    anomaly_type = db.Column(db.String(30))  # SPIKE | SUSTAINED_HIGH | SUDDEN_DROP | UNUSUAL_TIME | PATTERN_CHANGE
    status = db.Column(db.String(20), default="OPEN")
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    record = db.relationship("ConsumptionRecord", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "consumption_record_id": self.consumption_record_id,
            "timestamp": self.record.timestamp.isoformat() if self.record else None,
            "expected_kwh": self.expected_kwh,
            "actual_kwh": self.actual_kwh,
            "difference_kwh": self.difference_kwh,
            "percentage_difference": self.percentage_difference,
            "anomaly_score": self.anomaly_score,
            "severity": self.severity,
            "anomaly_type": self.anomaly_type,
            "status": self.status,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat(),
        }


class ModelRun(db.Model):
    __tablename__ = "model_runs"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(
        db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name = db.Column(db.String(60), nullable=False)
    training_records = db.Column(db.Integer, nullable=False)
    mae = db.Column(db.Float)
    rmse = db.Column(db.Float)
    mape = db.Column(db.Float)
    training_time = db.Column(db.Float)  # seconds
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    feature_importance = db.Column(db.JSON)
    run_group = db.Column(db.String(36), index=True)  # models trained together share a group
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "model_name": self.model_name,
            "training_records": self.training_records,
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "training_time": self.training_time,
            "is_active": self.is_active,
            "feature_importance": self.feature_importance,
            "run_group": self.run_group,
            "created_at": self.created_at.isoformat(),
        }


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id = db.Column(
        db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    anomaly_id = db.Column(db.Integer, db.ForeignKey("anomalies.id", ondelete="CASCADE"))
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(10), nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "anomaly_id": self.anomaly_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }


class TariffSetting(db.Model):
    """User-configured tariff. No official Kenya Power tariff is assumed."""

    __tablename__ = "tariff_settings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    cost_per_kwh = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="KES")
    effective_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cost_per_kwh": self.cost_per_kwh,
            "currency": self.currency,
            "effective_date": self.effective_date.isoformat(),
        }


class SystemSetting(db.Model):
    """Key/value JSON settings (e.g. anomaly thresholds), editable by admins."""

    __tablename__ = "system_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.JSON, nullable=False)
