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


def test_get_me_returns_current_user(client):
    client.post("/auth/register", json={"email": "dave@example.com", "password": "hunter2pass"})
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "dave@example.com"
    assert body["role"] == "contributor"
    assert "created_at" in body


def test_get_me_unauthenticated_rejected(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_change_password_then_login_with_new_password(client):
    client.post("/auth/register", json={"email": "erin@example.com", "password": "hunter2pass"})
    resp = client.post(
        "/auth/change-password", json={"current_password": "hunter2pass", "new_password": "new-hunter3pass"}
    )
    assert resp.status_code == 204

    client.post("/auth/logout")
    resp = client.post("/auth/login", json={"email": "erin@example.com", "password": "new-hunter3pass"})
    assert resp.status_code == 200
    resp = client.post("/auth/login", json={"email": "erin@example.com", "password": "hunter2pass"})
    assert resp.status_code == 401


def test_change_password_wrong_current_password_rejected(client):
    client.post("/auth/register", json={"email": "frank@example.com", "password": "hunter2pass"})
    resp = client.post(
        "/auth/change-password", json={"current_password": "wrong-pass", "new_password": "new-hunter3pass"}
    )
    assert resp.status_code == 400
