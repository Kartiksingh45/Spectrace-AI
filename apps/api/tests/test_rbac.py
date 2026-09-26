from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.checkpointer import get_checkpointer
from app.agent.schemas import GeneratedPlan
from app.api.deps import get_agent_overrides
from app.main import app
from app.models.user import User, UserRole


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


def _configure_agent(responses, plan_generator=lambda *a: _plan()):
    checkpointer = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: checkpointer
    app.dependency_overrides[get_agent_overrides] = lambda: {
        "agent_model": ScriptedModel(responses=responses),
        "classifier": lambda text: "feature",
        "plan_generator": plan_generator,
    }


def test_contributor_cannot_decide_on_a_plan(client, db_session):
    client.post("/auth/register", json={"email": "contributor@example.com", "password": "hunter2pass"})
    project = client.post("/projects", json={"name": "Demo"}).json()
    _configure_agent([_tool_call("generate_plan")])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    run = client.post(f"/requests/{change_request['id']}/analyse").json()

    # Registering user defaults to the "contributor" role, which may submit requests but not decide on them.
    resp = client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"})
    assert resp.status_code == 403

    app.dependency_overrides.pop(get_checkpointer, None)
    app.dependency_overrides.pop(get_agent_overrides, None)


def test_reviewer_can_decide_on_a_plan(client, db_session):
    client.post("/auth/register", json={"email": "reviewer@example.com", "password": "hunter2pass"})
    db_session.query(User).filter(User.email == "reviewer@example.com").update({"role": UserRole.reviewer})
    db_session.commit()
    project = client.post("/projects", json={"name": "Demo"}).json()
    _configure_agent([_tool_call("generate_plan")])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    run = client.post(f"/requests/{change_request['id']}/analyse").json()

    resp = client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    app.dependency_overrides.pop(get_checkpointer, None)
    app.dependency_overrides.pop(get_agent_overrides, None)


def test_non_administrator_cannot_list_or_update_users(client, db_session):
    client.post("/auth/register", json={"email": "plain@example.com", "password": "hunter2pass"})

    assert client.get("/auth/users").status_code == 403
    assert (
        client.patch(
            "/auth/users/00000000-0000-0000-0000-000000000000/role", json={"role": "administrator"}
        ).status_code
        == 403
    )


def test_administrator_can_list_and_update_users(client, db_session):
    client.post("/auth/register", json={"email": "admin@example.com", "password": "hunter2pass"})
    db_session.query(User).filter(User.email == "admin@example.com").update({"role": UserRole.administrator})
    db_session.commit()
    client.post("/auth/register", json={"email": "someone@example.com", "password": "hunter2pass"})

    # log back in as the administrator - registering "someone" above switched the session cookie.
    client.post("/auth/login", json={"email": "admin@example.com", "password": "hunter2pass"})

    users = client.get("/auth/users").json()
    assert {u["email"] for u in users} == {"admin@example.com", "someone@example.com"}

    someone = next(u for u in users if u["email"] == "someone@example.com")
    updated = client.patch(f"/auth/users/{someone['id']}/role", json={"role": "reviewer"}).json()
    assert updated["role"] == "reviewer"
