from app.extensions import db
from app.models.user import utcnow


class Household(db.Model):
    __tablename__ = "households"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(160))
    household_size = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "household_name": self.household_name,
            "location": self.location,
            "household_size": self.household_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
