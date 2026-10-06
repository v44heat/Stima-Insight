import io

import numpy as np
import pandas as pd
import pytest

from app.ml.preprocessing import SchemaError, clean_upload, to_regular_series


def raw(rows):
    return pd.DataFrame(rows, columns=["timestamp", "consumption_kwh"])


def test_missing_column_rejected():
    with pytest.raises(SchemaError):
        clean_upload(pd.DataFrame({"timestamp": ["2026-01-01"]}))


def test_validation_stats():
    df = raw([
        ["2026-01-01 00:00:00", "0.8"],
        ["2026-01-01 01:00:00", ""],           # missing -> interpolated
        ["2026-01-01 02:00:00", "1.0"],
        ["2026-01-01 02:00:00", "5.0"],        # duplicate timestamp
        ["2026-01-01 03:00:00", "-2"],         # negative -> invalid
        ["not a date", "1.0"],                 # bad timestamp -> invalid
        ["2026-01-01 04:00:00", "abc"],        # non numeric -> invalid
    ])
    r = clean_upload(df)
    assert r.stats == {"records_uploaded": 7, "valid_records": 3, "invalid_records": 3,
                       "duplicates_removed": 1, "missing_values_repaired": 1}
    assert r.data["consumption_kwh"].tolist() == [0.8, 0.9, 1.0]  # interpolated, not zero
    assert str(r.data["timestamp"].dt.tz) == "Africa/Nairobi"
    assert {e["row"] for e in r.errors} >= {5, 6, 7}


def test_offset_timestamps_converted_to_nairobi():
    r = clean_upload(raw([["2026-01-01T00:00:00Z", "1"], ["2026-01-01 04:00:00", "1"]]))
    assert r.data["timestamp"].iloc[0].hour == 3   # 00:00Z -> 03:00 EAT
    assert r.data["timestamp"].iloc[1].hour == 4   # naive treated as Nairobi


def test_resample_sums_energy_and_fills_gaps():
    idx = pd.date_range("2026-01-01", periods=96, freq="30min", tz="Africa/Nairobi")
    df = pd.DataFrame({"timestamp": idx, "consumption_kwh": 0.5})
    df = df.drop(index=[10, 11, 12])  # gap of 3 half-hours
    hourly = to_regular_series(df, "1h")
    assert len(hourly) == 48 and not hourly["consumption_kwh"].isna().any()
    assert hourly["consumption_kwh"].iloc[0] == pytest.approx(1.0)


def test_csv_upload_endpoint_and_isolation(client, auth_headers):
    client.post("/api/household", json={"household_name": "H1"}, headers=auth_headers)
    csv_text = "timestamp,consumption_kwh\n2026-01-01 00:00:00,0.82\n2026-01-01 01:00:00,0.76\n2026-01-01 01:00:00,0.9\n"
    r = client.post("/api/consumption/upload", headers=auth_headers,
                    data={"file": (io.BytesIO(csv_text.encode()), "d.csv")}, content_type="multipart/form-data")
    assert r.status_code == 201
    s = r.get_json()["data"]
    assert (s["records_uploaded"], s["valid_records"], s["duplicates_removed"], s["records_inserted"]) == (3, 2, 1, 2)
    # re-upload: nothing new inserted
    r = client.post("/api/consumption/upload", headers=auth_headers,
                    data={"file": (io.BytesIO(csv_text.encode()), "d.csv")}, content_type="multipart/form-data")
    assert r.get_json()["data"]["skipped_already_stored"] == 2
    lst = client.get("/api/consumption?search=2026-01-01", headers=auth_headers).get_json()
    assert lst["pagination"]["total"] == 2
    # another user cannot delete it
    tok = client.post("/api/auth/register", json={"name": "Other", "email": "o@example.com",
                      "password": "ChangeMe123!"}).get_json()["data"]["token"]
    oh = {"Authorization": f"Bearer {tok}"}
    client.post("/api/household", json={"household_name": "H2"}, headers=oh)
    rid = lst["data"][0]["id"]
    assert client.delete(f"/api/consumption/{rid}", headers=oh).status_code == 404


def test_upload_rejects_bad_files(client, auth_headers):
    client.post("/api/household", json={"household_name": "H1"}, headers=auth_headers)
    r = client.post("/api/consumption/upload", headers=auth_headers,
                    data={"file": (io.BytesIO(b"x"), "d.txt")}, content_type="multipart/form-data")
    assert r.status_code == 422
    r = client.post("/api/consumption/upload", headers=auth_headers,
                    data={"file": (io.BytesIO(b"a,b\n1,2\n"), "d.csv")}, content_type="multipart/form-data")
    assert r.status_code == 422 and "Missing required column" in r.get_json()["error"]["message"]


def test_manual_entry_and_duplicate(client, auth_headers):
    client.post("/api/household", json={"household_name": "H1"}, headers=auth_headers)
    body = {"date": "2026-02-01", "time": "19:00", "consumption_kwh": 2.4}
    assert client.post("/api/consumption", json=body, headers=auth_headers).status_code == 201
    assert client.post("/api/consumption", json=body, headers=auth_headers).status_code == 409
    assert client.post("/api/consumption", json={**body, "consumption_kwh": -1}, headers=auth_headers).status_code == 422


def test_demo_load_is_labelled_synthetic(client, auth_headers):
    client.post("/api/household", json={"household_name": "H1", "household_size": 4}, headers=auth_headers)
    r = client.post("/api/consumption/demo", json={"days": 30}, headers=auth_headers)
    assert r.status_code == 201 and r.get_json()["label"] == "Demo/Synthetic Data"
    assert r.get_json()["data"]["records_inserted"] == 30 * 24
