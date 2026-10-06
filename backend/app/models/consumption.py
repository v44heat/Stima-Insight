from app.extensions import db
from app.models.user import utcnow
from app.utils.timeutils import nairobi_iso


class ConsumptionRecord(db.Model):
    __tablename__ = "consumption_records"
    __table_args__ = (
        db.UniqueConstraint("household_id", "timestamp", name="uq_household_timestamp"),
        db.Index("ix_consumption_household_ts", "household_id", "timestamp"),
    )

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(
        db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    consumption_kwh = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    source = db.Column(db.String(20), default="manual")  # csv | manual | demo
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "timestamp": nairobi_iso(self.timestamp),
            "consumption_kwh": self.consumption_kwh,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "source": self.source,
        }
