import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.checkpointer import get_checkpointer
from app.agent.schemas import GeneratedPlan
from app.api.deps import get_agent_overrides
from app.main import app


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


@pytest.fixture()
def agent_overrides():
    """Lets a test script the agent's tool-calling decisions; cleared after the test.

    IMPORTANT: a fresh scripted model is constructed on *every* HTTP request (build_graph() is
    called anew per request, exactly like a real ChatGroq client would be) - it always starts
    reading its own `responses` list from index 0. So `configure(...)` must be called again,
    with just the response(s) that request's own agent turn(s) should produce, before *each*
    HTTP call that will trigger a new "agent" node invocation (not once for the whole scenario).
    """
    checkpointer = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: checkpointer

    def configure(responses, plan_generator=lambda *a: _plan()):
        app.dependency_overrides[get_agent_overrides] = lambda: {
            "agent_model": ScriptedModel(responses=responses),
            "classifier": lambda text: "feature",
            "plan_generator": plan_generator,
        }

    yield configure
    app.dependency_overrides.pop(get_checkpointer, None)
    app.dependency_overrides.pop(get_agent_overrides, None)


def _register_and_create_project(client, email="pm@example.com"):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    project = client.post("/projects", json={"name": "Demo"}).json()
    return project


def test_analyse_reaches_awaiting_approval(client, agent_overrides):
    project = _register_and_create_project(client)
    agent_overrides([_tool_call("generate_plan")])

    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()

    run = client.post(f"/requests/{change_request['id']}/analyse").json()

    assert run["status"] == "awaiting_approval"
    assert run["generated_plan"]["summary"] == "summary"
    assert any(step["tool_name"] == "generate_plan" for step in run["steps"])


def test_analyse_is_idempotent_while_in_flight(client, agent_overrides):
    project = _register_and_create_project(client)
    agent_overrides([_tool_call("generate_plan")])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()

    first = client.post(f"/requests/{change_request['id']}/analyse").json()
    # No new agent_overrides configured - if this call incorrectly started a second run, it would
    # need a second scripted response and fail; instead it should just return the in-flight run.
    second = client.post(f"/requests/{change_request['id']}/analyse").json()

    assert first["id"] == second["id"]


def test_clarification_flow_then_approval(client, agent_overrides):
    project = _register_and_create_project(client)
    agent_overrides([_tool_call("request_clarification", {"question": "When should OTP trigger?"})])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()

    run = client.post(f"/requests/{change_request['id']}/analyse").json()
    assert run["status"] == "awaiting_clarification"
    assert run["pending_question"] == "When should OTP trigger?"

    agent_overrides([_tool_call("generate_plan")])
    run = client.post(f"/runs/{run['id']}/clarification", json={"answer": "Before final submit"}).json()
    assert run["status"] == "awaiting_approval"

    decision = client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"}).json()
    assert decision["status"] == "completed"

    # analyse on an already-approved request should now refuse rather than silently re-running.
    resp = client.post(f"/requests/{change_request['id']}/analyse")
    assert resp.status_code == 400


def test_rejected_plan_is_never_marked_approved(client, agent_overrides):
    project = _register_and_create_project(client)
    agent_overrides([_tool_call("generate_plan")])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    run = client.post(f"/requests/{change_request['id']}/analyse").json()

    client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "rejected", "feedback": "not needed"})

    # A second decision on the same (now-resolved) plan must be refused, not silently accepted.
    resp = client.post(f"/plans/{run['plan_id']}/decision", json={"decision": "approved"})
    assert resp.status_code == 400


def test_regenerate_produces_new_plan_version(client, agent_overrides):
    project = _register_and_create_project(client)
    calls = {"n": 0}

    def plan_generator(request_text, request_type, evidence, feedback):
        calls["n"] += 1
        return _plan(confidence="low" if calls["n"] == 1 else "high")

    agent_overrides([_tool_call("generate_plan", call_id="1")], plan_generator=plan_generator)
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    run = client.post(f"/requests/{change_request['id']}/analyse").json()
    first_plan_id = run["plan_id"]

    agent_overrides([_tool_call("generate_plan", call_id="2")], plan_generator=plan_generator)
    run = client.post(
        f"/plans/{first_plan_id}/decision", json={"decision": "regenerate_requested", "feedback": "add detail"}
    ).json()

    assert calls["n"] == 2
    assert run["status"] == "awaiting_approval"
    assert run["plan_id"] != first_plan_id
    assert run["generated_plan"]["confidence"] == "high"


def test_second_user_cannot_see_or_analyse_first_users_request(client, agent_overrides):
    project = _register_and_create_project(client, email="owner@example.com")
    agent_overrides([_tool_call("generate_plan")])
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    client.post("/auth/logout")

    client.post("/auth/register", json={"email": "intruder@example.com", "password": "hunter2pass"})
    resp = client.post(f"/requests/{change_request['id']}/analyse")
    assert resp.status_code == 404
