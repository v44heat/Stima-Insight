"""End-to-end test of the demonstration workflow (steps 1-15 of the spec)."""
import pytest


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.slow
def test_full_demo_workflow(client):
    # 1-2. register + household
    tok = client.post("/api/auth/register", json={"name": "Demo", "email": "demo@example.com",
                                                  "password": "ChangeMe123!"}).get_json()["data"]["token"]
    assert client.post("/api/household", json={"household_name": "Demo Home", "household_size": 4},
                       headers=h(tok)).status_code == 201
    # 3-4. import (synthetic demo data)
    r = client.post("/api/consumption/demo", json={"days": 70, "start": "2026-01-01"}, headers=h(tok))
    assert r.status_code == 201 and r.get_json()["data"]["records_inserted"] == 70 * 24

    # forecasting/training needs a model first
    assert client.post("/api/forecast/generate", json={"horizon": "24h"}, headers=h(tok)).status_code == 404

    # 5. train, 6. performance
    r = client.post("/api/ml/train", json={}, headers=h(tok))
    assert r.status_code == 201, r.get_json()
    train = r.get_json()["data"]
    assert train["selected_model"] in ("Random Forest", "SARIMA")
    assert {x["model_name"] for x in train["runs"]} == {"Random Forest", "SARIMA"}

    perf = client.get("/api/ml/performance", headers=h(tok)).get_json()["data"]
    for run in perf["comparison"]:
        assert run["mae"] > 0 and run["rmse"] >= run["mae"]       # real, internally consistent metrics
    assert perf["includes_synthetic_data"] is True
    imp = perf["feature_importance"]
    assert imp and abs(sum(imp.values()) - 1.0) < 1e-6              # computed from the model

    # 7-8. forecast
    r = client.post("/api/forecast/generate", json={"horizon": "3d"}, headers=h(tok))
    assert r.status_code == 201
    fc = r.get_json()["data"]
    assert len(fc["points"]) == 72
    assert all(p["lower_bound"] <= p["predicted_kwh"] <= p["upper_bound"] for p in fc["points"])
    assert fc["expected_total_kwh"] == pytest.approx(sum(p["predicted_kwh"] for p in fc["points"]), rel=1e-3)
    assert client.get("/api/forecast/export", headers=h(tok)).status_code == 200

    before = client.get("/api/anomalies/summary", headers=h(tok)).get_json()["data"]["total"]
    assert before > 0   # injected synthetic anomalies were detected

    # 9-11. introduce an abnormal night-time reading right after the data ends
    last = client.get("/api/consumption?sort=timestamp&order=desc&per_page=1", headers=h(tok)).get_json()["data"][0]
    assert last["timestamp"].startswith("2026-03-11T23:00")
    r = client.post("/api/consumption", headers=h(tok),
                    json={"date": "2026-03-12", "time": "00:00", "consumption_kwh": 4.0})
    assert r.status_code == 201
    assert r.get_json()["detection"]["created"] >= 1

    items = client.get("/api/anomalies?start=2026-03-12&end=2026-03-12", headers=h(tok)).get_json()["data"]
    a = next(x for x in items if x["timestamp"].startswith("2026-03-12T00:00"))
    # 12. numbers are calculated, not hard-coded
    assert a["actual_kwh"] == 4.0
    assert a["difference_kwh"] == pytest.approx(a["actual_kwh"] - a["expected_kwh"])
    pct = (a["actual_kwh"] - a["expected_kwh"]) / max(a["expected_kwh"], 0.05) * 100
    assert a["percentage_difference"] == pytest.approx(pct, rel=1e-6)   # true, unclipped deviation
    assert a["severity"] == "CRITICAL" and a["anomaly_type"] == "UNUSUAL_TIME"
    assert "•" in a["explanation"] and "appliance" not in a["explanation"].lower()

    # 13. alert generated; 14. detail; 15. export
    alerts = client.get("/api/alerts?unread=true", headers=h(tok)).get_json()
    assert alerts["unread_count"] >= 1
    mine = next(x for x in alerts["data"] if x["anomaly_id"] == a["id"])
    assert "above the expected pattern" in mine["message"]
    assert client.patch(f"/api/alerts/{mine['id']}/read", headers=h(tok)).get_json()["data"]["is_read"]
    assert client.post("/api/alerts/read-all", headers=h(tok)).status_code == 200
    assert client.get(f"/api/anomalies/{a['id']}", headers=h(tok)).status_code == 200
    csv_text = client.get("/api/anomalies/export", headers=h(tok)).get_data(as_text=True)
    assert "percentage_difference" in csv_text and "2026-03-12T00:00" in csv_text

    # dashboard
    s = client.get("/api/dashboard/summary", headers=h(tok)).get_json()["data"]
    assert s["has_data"] and s["synthetic_label"] == "Demo/Synthetic Data"
    assert s["headline_alert"]["message"].startswith("Abnormal consumption detected")
    assert s["total_consumption_kwh"] > 0 and s["anomalies_detected"] > 0
    for res in ("hourly", "daily", "weekly"):
        c = client.get(f"/api/dashboard/chart?resolution={res}", headers=h(tok))
        assert c.status_code == 200, c.get_json()
        assert c.get_json()["data"]["points"]
    assert client.get("/api/reports/summary.pdf", headers=h(tok)).data[:4] == b"%PDF"

    # thresholds are configurable by admins only
    assert client.put("/api/settings/thresholds", json={"low": 5}, headers=h(tok)).status_code == 403
