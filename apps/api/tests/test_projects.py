import io

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.checkpointer import get_checkpointer
from app.agent.schemas import GeneratedPlan
from app.api.deps import get_agent_overrides, get_brd_generator
from app.main import app
from app.models.user import User, UserRole
from app.schemas.brd import BrdInput, GeneratedBrd


class ScriptedModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def _tool_call(name: str, args: dict | None = None, call_id: str = "1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])


def _plan(**overrides) -> GeneratedPlan:
    base = dict(
        summary="summary",
        request_type="feature",
        questions=[],
        evidence=[],
        affected_files=[],
        user_story="As a user...",
        acceptance_criteria=["works"],
        tasks=[],
        test_cases=[],
        confidence="low",
    )
    base.update(overrides)
    return GeneratedPlan(**base)


def _register(client, email, password="hunter2pass"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp


def _fake_brd(payload: BrdInput) -> GeneratedBrd:
    return GeneratedBrd(
        executive_summary="summary",
        business_objectives=["objective"],
        in_scope=["in"],
        out_of_scope=["out"],
        stakeholders=["stakeholder"],
        functional_requirements=[
            {"description": "req one", "priority": "must_have"},
            {"description": "req two", "priority": "should_have"},
        ],
        non_functional_requirements=[{"description": "req three", "priority": "could_have"}],
        success_criteria=["criteria"],
    )


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


def test_only_owner_can_delete_project(client):
    _register(client, "judy@example.com")
    project = client.post("/projects", json={"name": "Original"}).json()
    client.post("/auth/logout")

    _register(client, "karl@example.com")
    resp = client.delete(f"/projects/{project['id']}")
    assert resp.status_code == 404


def test_deleting_a_project_removes_all_its_dependent_rows(client, db_session):
    """No FK in this schema cascades on delete, so a project with a document (-> content chunk),
    a change request, an agent run/step, a generated plan, and an approval all attached exercises
    every table delete_project has to clear before Postgres will allow the project row itself to
    go - a naive single db.delete(project) would fail with a foreign key violation here."""
    _register(client, "liam@example.com")
    db_session.query(User).filter(User.email == "liam@example.com").update({"role": UserRole.reviewer})
    db_session.commit()
    project = client.post("/projects", json={"name": "To delete"}).json()

    client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Some requirement text."), "text/plain")},
    )

    checkpointer = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: checkpointer
    app.dependency_overrides[get_agent_overrides] = lambda: {
        "agent_model": ScriptedModel(responses=[_tool_call("generate_plan")]),
        "classifier": lambda text: "feature",
        "plan_generator": lambda *a: _plan(),
    }
    try:
        change_request = client.post(
            f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
        ).json()
        started = client.post(f"/requests/{change_request['id']}/analyse").json()
        run = client.get(f"/runs/{started['id']}").json()
        assert run["status"] == "awaiting_approval"
        client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"})
    finally:
        app.dependency_overrides.pop(get_checkpointer, None)
        app.dependency_overrides.pop(get_agent_overrides, None)

    resp = client.delete(f"/projects/{project['id']}")
    assert resp.status_code == 204

    assert client.get(f"/projects/{project['id']}").status_code == 404
    assert client.get("/projects").json() == []


def test_new_project_has_draft_status_and_no_requirement_count(client):
    _register(client, "mia@example.com")
    project = client.post("/projects", json={"name": "Fresh"}).json()
    assert project["status"] == "draft"
    assert project["requirement_count"] is None


def test_project_status_becomes_in_progress_after_activity(client):
    _register(client, "noah@example.com")
    project = client.post("/projects", json={"name": "Active"}).json()
    client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(b"Some requirement text."), "text/plain")},
    )

    resp = client.get(f"/projects/{project['id']}").json()
    assert resp["status"] == "in_progress"


def test_project_status_becomes_complete_after_an_approved_plan(client, db_session):
    _register(client, "olivia@example.com")
    db_session.query(User).filter(User.email == "olivia@example.com").update({"role": UserRole.reviewer})
    db_session.commit()
    project = client.post("/projects", json={"name": "Shippable"}).json()

    checkpointer = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: checkpointer
    app.dependency_overrides[get_agent_overrides] = lambda: {
        "agent_model": ScriptedModel(responses=[_tool_call("generate_plan")]),
        "classifier": lambda text: "feature",
        "plan_generator": lambda *a: _plan(),
    }
    try:
        change_request = client.post(
            f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
        ).json()
        started = client.post(f"/requests/{change_request['id']}/analyse").json()
        run = client.get(f"/runs/{started['id']}").json()
        client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"})
    finally:
        app.dependency_overrides.pop(get_checkpointer, None)
        app.dependency_overrides.pop(get_agent_overrides, None)

    resp = client.get(f"/projects/{project['id']}").json()
    assert resp["status"] == "complete"


def test_project_requirement_count_reflects_latest_brd(client):
    _register(client, "peter@example.com")
    project = client.post("/projects", json={"name": "With BRD"}).json()

    app.dependency_overrides[get_brd_generator] = lambda: _fake_brd
    try:
        client.post(
            f"/projects/{project['id']}/brd",
            json={
                "project_name": "With BRD",
                "background": "background",
                "objectives": "objectives",
                "target_users": "users",
                "key_features": "features",
            },
        )
    finally:
        app.dependency_overrides.pop(get_brd_generator, None)

    resp = client.get(f"/projects/{project['id']}").json()
    assert resp["requirement_count"] == 3


def test_renaming_a_project_bumps_updated_at(client):
    _register(client, "quinn@example.com")
    project = client.post("/projects", json={"name": "Before"}).json()
    renamed = client.patch(f"/projects/{project['id']}", json={"name": "After"}).json()
    assert renamed["updated_at"] >= project["updated_at"]
