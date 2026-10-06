"""Create tables, an admin, a demo user + household, load SYNTHETIC demo data and train models.

Run once after creating the PostgreSQL database:
    python seed_database.py            (add --no-train to skip model training)

DEVELOPMENT/DEMO credentials only (override with ADMIN_EMAIL/ADMIN_PASSWORD/DEMO_EMAIL/DEMO_PASSWORD).
"""
import argparse
import os
from datetime import date

import pandas as pd

from app import create_app
from app.extensions import db
from app.ml.synthetic import generate_household
from app.models import ConsumptionRecord, Household, TariffSetting, User
from app.services.ingestion import store_dataframe
from app.services.settings_service import get_thresholds, save_thresholds
from app.services.training_service import train_household

ADMIN = (os.getenv("ADMIN_EMAIL", "admin@example.com"), os.getenv("ADMIN_PASSWORD", "ChangeMe123!"))
DEMO = (os.getenv("DEMO_EMAIL", "demo@example.com"), os.getenv("DEMO_PASSWORD", "ChangeMe123!"))


def ensure_user(name, email, password, role):
    u = User.query.filter_by(email=email).first()
    if u is None:
        u = User(name=name, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print(f"created {role.lower()} account: {email}")
    return u


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-train", action="store_true")
    p.add_argument("--days", type=int, default=180)
    a = p.parse_args()

    app = create_app()
    with app.app_context():
        db.create_all()
        print("1. tables ready")
        ensure_user("Administrator", *ADMIN[:1], ADMIN[1], "ADMIN")
        demo = ensure_user("Demo User", DEMO[0], DEMO[1], "USER")
        print("2. admin + demo accounts ready")

        if TariffSetting.query.count() == 0:
            db.session.add(TariffSetting(name="Demo tariff (configured value, NOT an official rate)",
                                         cost_per_kwh=25.0, currency="KES", effective_date=date(2026, 1, 1)))
            db.session.commit()
        save_thresholds(get_thresholds())      # persist defaults so they are visible/editable
        print("3. default tariff + anomaly thresholds saved (edit them in the admin settings)")

        h = Household.query.filter_by(user_id=demo.id).first()
        if h is None:
            h = Household(user_id=demo.id, household_name="Demo Household (Nairobi)",
                          location="Nairobi, Kenya", household_size=4)
            db.session.add(h)
            db.session.commit()
        print("4. demo household ready")

        if ConsumptionRecord.query.filter_by(household_id=h.id).count() == 0:
            data, labels = generate_household(start="2026-01-01", days=a.days, household_size=4, seed=42)
            stats = store_dataframe(h.id, data.assign(timestamp=data["timestamp"].astype(str)), "demo")["stats"]
            print(f"5. loaded SYNTHETIC demo data: {stats['records_inserted']} hourly records "
                  f"({len(labels)} injected anomalies)")
        else:
            print("5. demo data already present")

        if not a.no_train:
            print("6. training models (about a minute)...")
            r = train_household(h.id)
            print(f"   selected model: {r['selected_model']} | detection: {r['detection']}")

    print("\nDEV/DEMO login (not for production):")
    print(f"  user : {DEMO[0]} / {DEMO[1]}")
    print(f"  admin: {ADMIN[0]} / {ADMIN[1]}")


if __name__ == "__main__":
    main()
