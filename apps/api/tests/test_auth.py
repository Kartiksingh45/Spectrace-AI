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


def _capture_reset_url(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "app.api.routes.auth.send_password_reset_email", lambda to, url: sent.update(to=to, url=url)
    )
    return sent


def test_forgot_password_then_reset_with_new_password(client, monkeypatch):
    client.post("/auth/register", json={"email": "grace@example.com", "password": "hunter2pass"})
    sent = _capture_reset_url(monkeypatch)

    resp = client.post("/auth/forgot-password", json={"email": "grace@example.com"})
    assert resp.status_code == 204
    assert sent["to"] == "grace@example.com"
    token = sent["url"].split("token=")[1]

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass1"})
    assert resp.status_code == 204

    client.post("/auth/logout")
    resp = client.post("/auth/login", json={"email": "grace@example.com", "password": "brand-new-pass1"})
    assert resp.status_code == 200
    # The old password must no longer work.
    resp = client.post("/auth/login", json={"email": "grace@example.com", "password": "hunter2pass"})
    assert resp.status_code == 401


def test_forgot_password_unknown_email_still_returns_204_and_sends_nothing(client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.api.routes.auth.send_password_reset_email", lambda to, url: calls.append(to))
    resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 204
    assert calls == []


def test_reset_password_unknown_token_rejected(client):
    resp = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever123"})
    assert resp.status_code == 400


def test_reset_password_token_cannot_be_reused(client, monkeypatch):
    client.post("/auth/register", json={"email": "henry@example.com", "password": "hunter2pass"})
    sent = _capture_reset_url(monkeypatch)
    client.post("/auth/forgot-password", json={"email": "henry@example.com"})
    token = sent["url"].split("token=")[1]

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "first-new-pass1"})
    assert resp.status_code == 204
    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "second-new-pass1"})
    assert resp.status_code == 400


def test_reset_password_expired_token_rejected(client, monkeypatch, db_session):
    from datetime import datetime, timedelta, timezone

    from app.models.user import User

    client.post("/auth/register", json={"email": "iris@example.com", "password": "hunter2pass"})
    sent = _capture_reset_url(monkeypatch)
    client.post("/auth/forgot-password", json={"email": "iris@example.com"})
    token = sent["url"].split("token=")[1]

    user = db_session.query(User).filter(User.email == "iris@example.com").first()
    user.reset_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass1"})
    assert resp.status_code == 400
