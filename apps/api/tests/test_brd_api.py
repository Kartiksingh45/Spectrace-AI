import pytest

from app.api.deps import get_brd_generator
from app.main import app
from app.schemas.brd import BrdInput, GeneratedBrd


def _fake_brd(payload: BrdInput) -> GeneratedBrd:
    return GeneratedBrd(
        executive_summary=f"Summary for {payload.project_name}",
        business_objectives=["Ship the thing"],
        in_scope=["Core feature"],
        out_of_scope=["Mobile app"],
        stakeholders=["Product owner"],
        functional_requirements=[{"description": "Users can log in", "priority": "must_have"}],
        non_functional_requirements=[{"description": "p95 latency under 200ms", "priority": "should_have"}],
        assumptions=["Users already have accounts"],
        constraints=["Must ship in Q1"],
        risks=["Third-party API may rate-limit"],
        success_criteria=["95% of users complete signup"],
    )


@pytest.fixture()
def brd_generator():
    app.dependency_overrides[get_brd_generator] = lambda: _fake_brd
    yield
    app.dependency_overrides.pop(get_brd_generator, None)


def _register_and_create_project(client, email="brd@example.com"):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    return client.post("/projects", json={"name": "Demo"}).json()


def _brd_payload(**overrides):
    base = dict(
        project_name="Loan Portal",
        background="Manual loan approval is slow and error-prone.",
        objectives="Automate approval decisions and cut turnaround time.",
        target_users="Loan officers and applicants",
        key_features="Document upload, automated eligibility checks, status tracking",
    )
    base.update(overrides)
    return base


def test_generate_brd_saves_and_returns_document(client, brd_generator):
    project = _register_and_create_project(client)

    resp = client.post(f"/projects/{project['id']}/brd", json=_brd_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"]["executive_summary"] == "Summary for Loan Portal"
    assert body["inputs"]["project_name"] == "Loan Portal"
    assert body["project_id"] == project["id"]


def test_list_brd_documents_returns_saved_ones(client, brd_generator):
    project = _register_and_create_project(client)
    client.post(f"/projects/{project['id']}/brd", json=_brd_payload())
    client.post(f"/projects/{project['id']}/brd", json=_brd_payload(project_name="Second BRD"))

    resp = client.get(f"/projects/{project['id']}/brd")
    assert resp.status_code == 200
    names = {doc["inputs"]["project_name"] for doc in resp.json()}
    assert names == {"Second BRD", "Loan Portal"}


def test_brd_is_project_scoped(client, brd_generator):
    project_a = _register_and_create_project(client, email="a@example.com")
    client.post("/auth/logout")
    _register_and_create_project(client, email="b@example.com")

    resp = client.get(f"/projects/{project_a['id']}/brd")
    assert resp.status_code == 404


def test_delete_brd_document(client, brd_generator):
    project = _register_and_create_project(client)
    doc = client.post(f"/projects/{project['id']}/brd", json=_brd_payload()).json()

    resp = client.delete(f"/projects/{project['id']}/brd/{doc['id']}")
    assert resp.status_code == 204
    assert client.get(f"/projects/{project['id']}/brd").json() == []


def test_generate_brd_failure_returns_502(client):
    def _raising_generator(payload):
        raise RuntimeError("model unavailable")

    app.dependency_overrides[get_brd_generator] = lambda: _raising_generator
    try:
        project = _register_and_create_project(client)
        resp = client.post(f"/projects/{project['id']}/brd", json=_brd_payload())
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.pop(get_brd_generator, None)


def test_deleting_a_project_removes_its_brd_documents(client, brd_generator):
    project = _register_and_create_project(client)
    client.post(f"/projects/{project['id']}/brd", json=_brd_payload())

    resp = client.delete(f"/projects/{project['id']}")
    assert resp.status_code == 204
