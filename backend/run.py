"""Start the API on http://127.0.0.1:5000 (creates any missing tables first)."""
import os

from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # safe to repeat: only creates tables that do not exist yet
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_ENV", "development") != "production")
