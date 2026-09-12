def _register(client, email, password="hunter2pass"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp


def test_create_and_list_project(client):
    _register(client, "dana@example.com")
    resp = client.post("/projects", json={"name": "OTP Rollout"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "OTP Rollout"

    resp = client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_projects_are_isolated_between_users(client):
    _register(client, "erin@example.com")
    client.post("/projects", json={"name": "Erin's Project"})
    client.post("/auth/logout")

    _register(client, "frank@example.com")
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_only_owner_can_rename_project(client):
    _register(client, "grace@example.com")
    project = client.post("/projects", json={"name": "Original"}).json()
    client.post("/auth/logout")

    _register(client, "heidi@example.com")
    resp = client.patch(f"/projects/{project['id']}", json={"name": "Hijacked"})
    assert resp.status_code == 404
