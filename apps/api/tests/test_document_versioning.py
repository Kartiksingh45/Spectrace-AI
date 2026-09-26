import io


def _register_and_create_project(client, email="versioning@example.com"):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    return client.post("/projects", json={"name": "Demo"}).json()


def test_reuploading_same_filename_creates_a_new_version(client):
    project = _register_and_create_project(client)

    first = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Version one of the requirement text."), "text/plain")},
    ).json()
    assert first["version"] == 1
    assert first["previous_version_id"] is None

    second = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Version two of the requirement text, revised."), "text/plain")},
    ).json()
    assert second["version"] == 2
    assert second["previous_version_id"] == first["id"]


def test_diff_between_two_versions_shows_the_change(client):
    project = _register_and_create_project(client)

    first = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"OTP is optional for loan applications."), "text/plain")},
    ).json()
    second = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"OTP is mandatory for loan applications."), "text/plain")},
    ).json()

    diff = client.get(
        f"/projects/{project['id']}/documents/{second['id']}/diff", params={"against": first["id"]}
    ).json()

    assert diff["from_version"] == 1
    assert diff["to_version"] == 2
    joined = "\n".join(diff["diff_lines"])
    assert "-OTP is optional for loan applications." in joined
    assert "+OTP is mandatory for loan applications." in joined


def test_diff_requires_both_documents_to_be_ready(client):
    project = _register_and_create_project(client)

    ready = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Some ready requirement text."), "text/plain")},
    ).json()
    failed = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("unsupported.xyz", io.BytesIO(b"whatever"), "application/octet-stream")},
    ).json()
    assert failed["status"] == "failed"

    resp = client.get(f"/projects/{project['id']}/documents/{ready['id']}/diff", params={"against": failed["id"]})
    assert resp.status_code == 400


def test_deleting_an_older_version_that_is_still_referenced_succeeds(client):
    project = _register_and_create_project(client)

    first = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Version one."), "text/plain")},
    ).json()
    second = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Version two."), "text/plain")},
    ).json()
    assert second["previous_version_id"] == first["id"]

    resp = client.delete(f"/projects/{project['id']}/documents/{first['id']}")
    assert resp.status_code == 204

    documents = client.get(f"/projects/{project['id']}/documents").json()
    remaining = next(d for d in documents if d["id"] == second["id"])
    assert remaining["previous_version_id"] is None


def test_diff_is_project_scoped(client):
    project_a = _register_and_create_project(client, email="a@example.com")
    doc_a1 = client.post(
        f"/projects/{project_a['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Project A text one."), "text/plain")},
    ).json()
    doc_a2 = client.post(
        f"/projects/{project_a['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Project A text two."), "text/plain")},
    ).json()
    client.post("/auth/logout")

    project_b = _register_and_create_project(client, email="b@example.com")
    resp = client.get(f"/projects/{project_b['id']}/documents/{doc_a2['id']}/diff", params={"against": doc_a1["id"]})
    assert resp.status_code == 404
