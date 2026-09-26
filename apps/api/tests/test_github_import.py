import io
import zipfile
from unittest.mock import patch

from app.services.github_import import GithubImportError


def _make_repo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # GitHub's codeload zips nest everything under "{repo}-{branch}/".
        zf.writestr("demo-main/src/otp.py", "def verify_otp():\n    return True\n")
        zf.writestr("demo-main/node_modules/pkg/index.js", "module.exports = {};")
        zf.writestr("demo-main/README.md", "# demo")
    return buf.getvalue()


def _register_and_create_project(client, email="ghimport@example.com"):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    return client.post("/projects", json={"name": "Demo"}).json()


@patch("app.api.routes.documents.download_repo_zip")
def test_github_import_ingests_a_public_repo(mock_download, client):
    mock_download.return_value = _make_repo_zip()
    project = _register_and_create_project(client)

    doc = client.post(
        f"/projects/{project['id']}/github-import",
        json={"owner": "octocat", "repo": "demo", "branch": "main"},
    ).json()

    assert doc["status"] == "ready"
    assert doc["kind"] == "code"
    assert doc["filename"] == "octocat/demo@main"
    mock_download.assert_called_once_with("octocat", "demo", "main", max_bytes=50 * 1024 * 1024)


@patch("app.api.routes.documents.download_repo_zip")
def test_github_import_reports_repo_not_found(mock_download, client):
    mock_download.side_effect = GithubImportError("Repository octocat/missing (branch 'main') was not found, or is private")
    project = _register_and_create_project(client)

    resp = client.post(
        f"/projects/{project['id']}/github-import",
        json={"owner": "octocat", "repo": "missing"},
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


@patch("app.api.routes.documents.download_repo_zip")
def test_github_import_is_project_scoped(mock_download, client):
    mock_download.return_value = _make_repo_zip()
    client.post("/auth/register", json={"email": "a@example.com", "password": "hunter2pass"})
    client.post("/auth/logout")
    client.post("/auth/register", json={"email": "b@example.com", "password": "hunter2pass"})
    other_project = client.post("/projects", json={"name": "B"}).json()
    client.post("/auth/logout")

    client.post("/auth/login", json={"email": "a@example.com", "password": "hunter2pass"})
    resp = client.post(
        f"/projects/{other_project['id']}/github-import",
        json={"owner": "octocat", "repo": "demo"},
    )
    assert resp.status_code == 404
