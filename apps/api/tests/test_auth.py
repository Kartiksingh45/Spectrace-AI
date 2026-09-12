def test_register_then_login(client):
    resp = client.post("/auth/register", json={"email": "alice@example.com", "password": "hunter2pass"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "alice@example.com"
    assert "spectrace_session" in resp.cookies

    resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "hunter2pass"})
    assert resp.status_code == 200


def test_register_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "bob@example.com", "password": "hunter2pass"})
    resp = client.post("/auth/register", json={"email": "bob@example.com", "password": "another-pass"})
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post("/auth/register", json={"email": "carol@example.com", "password": "hunter2pass"})
    resp = client.post("/auth/login", json={"email": "carol@example.com", "password": "wrong-pass"})
    assert resp.status_code == 401


def test_unauthenticated_request_rejected(client):
    resp = client.get("/projects")
    assert resp.status_code == 401
