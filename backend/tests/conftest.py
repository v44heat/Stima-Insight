import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app(TestConfig)
    app.config["TRAINED_MODELS_DIR"] = str(tmp_path)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    r = client.post("/api/auth/register", json={
        "name": "Test User", "email": "test@example.com", "password": "ChangeMe123!"})
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}
