def test_register_and_login(client):
    r = client.post("/api/auth/register", json={
        "name": "Amina", "email": "amina@example.com", "password": "ChangeMe123!"})
    assert r.status_code == 201
    assert "password" not in str(r.get_json()["data"]["user"]).lower().replace("password_hash", "")
    r = client.post("/api/auth/login", json={"email": "amina@example.com", "password": "ChangeMe123!"})
    assert r.status_code == 200 and r.get_json()["data"]["token"]


def test_duplicate_email_rejected(client):
    body = {"name": "Amina", "email": "a@example.com", "password": "ChangeMe123!"}
    client.post("/api/auth/register", json=body)
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_validation_errors(client):
    r = client.post("/api/auth/register", json={"name": "A", "email": "bad", "password": "x"})
    assert r.status_code == 422
    assert set(r.get_json()["error"]["details"]) == {"name", "email", "password"}


def test_wrong_password(client, auth_headers):
    r = client.post("/api/auth/login", json={"email": "test@example.com", "password": "nope"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/household").status_code == 401


def test_household_isolation(client, auth_headers):
    r = client.post("/api/household", json={"household_name": "Kilimani Home", "household_size": 4},
                    headers=auth_headers)
    assert r.status_code == 201
    other = client.post("/api/auth/register", json={
        "name": "Other", "email": "o@example.com", "password": "ChangeMe123!"}).get_json()["data"]["token"]
    r = client.get("/api/household", headers={"Authorization": f"Bearer {other}"})
    assert r.status_code == 404  # other user cannot see first user's household
