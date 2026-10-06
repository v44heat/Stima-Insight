from datetime import date

from app.extensions import db
from app.models import User


def make_admin(client, app):
    client.post("/api/auth/register", json={"name": "Admin", "email": "admin@example.com", "password": "ChangeMe123!"})
    with app.app_context():
        u = User.query.filter_by(email="admin@example.com").first()
        u.role = "ADMIN"
        db.session.commit()
    t = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "ChangeMe123!"}).get_json()["data"]["token"]
    return {"Authorization": f"Bearer {t}"}


def test_admin_endpoints_require_admin(client, auth_headers):
    for path in ("/api/admin/stats", "/api/admin/users", "/api/admin/households", "/api/admin/models"):
        assert client.get(path, headers=auth_headers).status_code == 403
    assert client.get("/api/admin/stats").status_code == 401


def test_admin_stats_and_user_management(client, app, auth_headers):
    adm = make_admin(client, app)
    s = client.get("/api/admin/stats", headers=adm).get_json()["data"]
    assert s["total_users"] == 2 and s["total_anomalies"] == 0
    users = client.get("/api/admin/users", headers=adm).get_json()["data"]
    other = next(u for u in users if u["email"] == "test@example.com")
    assert client.patch(f"/api/admin/users/{other['id']}", json={"role": "BOSS"}, headers=adm).status_code == 422
    me = next(u for u in users if u["email"] == "admin@example.com")
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "USER"}, headers=adm).status_code == 422
    assert client.delete(f"/api/admin/users/{other['id']}", headers=adm).status_code == 200


def test_tariff_and_cost_estimate(client, app, auth_headers):
    adm = make_admin(client, app)
    assert client.get("/api/settings/tariff", headers=auth_headers).get_json()["data"] is None
    bad = client.put("/api/settings/tariff", json={"name": "", "cost_per_kwh": -1}, headers=adm)
    assert bad.status_code == 422
    ok = client.put("/api/settings/tariff", headers=adm, json={
        "name": "Test tariff", "cost_per_kwh": 20, "currency": "kes", "effective_date": "2026-01-01"})
    assert ok.status_code == 200 and ok.get_json()["data"]["currency"] == "KES"
    from app.services.settings_service import estimate_cost
    with app.app_context():
        c = estimate_cost(8.4)
    assert c["amount"] == 168.0 and c["is_estimate"] is True


def test_thresholds_validation(client, app):
    adm = make_admin(client, app)
    assert client.put("/api/settings/thresholds", json={"low": 30, "medium": 20}, headers=adm).status_code == 422
    r = client.put("/api/settings/thresholds", json={"low": 8, "medium": 18, "high": 30, "critical": 60}, headers=adm)
    assert r.status_code == 200 and r.get_json()["data"]["critical"] == 60
