from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.agent.checkpointer import get_checkpointer
from app.agent.schemas import GeneratedPlan
from app.api.deps import get_agent_overrides
from app.main import app

from langgraph.checkpoint.memory import InMemorySaver


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
        confidence="high",
    )
    base.update(overrides)
    return GeneratedPlan(**base)


@pytest.fixture()
def agent_overrides():
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


def _register_and_create_project(client, email="reviewer@example.com"):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass"})
    return client.post("/projects", json={"name": "Demo"}).json()


def test_create_list_and_delete_case(client):
    project = _register_and_create_project(client)

    created = client.post(
        f"/projects/{project['id']}/evaluation/cases",
        json={
            "title": "Clear OTP case",
            "request_text": "Add mobile OTP verification",
            "category": "clear",
            "expected_behavior": "direct_answer",
            "expected_sources": ["src/otp.py"],
        },
    ).json()
    assert created["title"] == "Clear OTP case"

    listed = client.get(f"/projects/{project['id']}/evaluation/cases").json()
    assert len(listed) == 1

    resp = client.delete(f"/projects/{project['id']}/evaluation/cases/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/projects/{project['id']}/evaluation/cases").json() == []


def test_run_with_no_cases_is_rejected(client, agent_overrides):
    # agent_overrides is only needed here to swap in an in-memory checkpointer: FastAPI resolves
    # Depends(get_checkpointer) before the route body runs its no-cases check, and the real
    # checkpointer would otherwise try (and hang) dialing Postgres against the test's sqlite URL.
    project = _register_and_create_project(client)
    resp = client.post(f"/projects/{project['id']}/evaluation/run")
    assert resp.status_code == 400


def test_run_dataset_and_report_end_to_end(client, agent_overrides):
    project = _register_and_create_project(client)
    client.post(
        f"/projects/{project['id']}/evaluation/cases",
        json={
            "title": "Clear OTP case",
            "request_text": "Add mobile OTP verification",
            "category": "clear",
            "expected_behavior": "direct_answer",
            "expected_sources": ["src/otp.py"],
        },
    )
    agent_overrides([_tool_call("generate_plan")])

    with patch("app.services.evaluation._retrieved_sources", return_value=["src/otp.py"]):
        results = client.post(f"/projects/{project['id']}/evaluation/run").json()

    assert len(results) == 1
    assert results[0]["actual_behavior"] == "direct_answer"
    assert results[0]["passed"] is True

    report = client.get(f"/projects/{project['id']}/evaluation/report").json()
    assert report["total_cases"] == 1
    assert report["retrieval_hit_rate"] == 1.0
    assert report["overall_pass_rate"] == 1.0


def test_evaluation_is_project_scoped(client):
    project_a = _register_and_create_project(client, email="a@example.com")
    client.post(
        f"/projects/{project_a['id']}/evaluation/cases",
        json={
            "title": "A's case",
            "request_text": "Do the thing",
            "category": "clear",
            "expected_behavior": "direct_answer",
        },
    )
    client.post("/auth/logout")

    project_b = _register_and_create_project(client, email="b@example.com")
    assert client.get(f"/projects/{project_b['id']}/evaluation/cases").json() == []
    resp = client.get(f"/projects/{project_a['id']}/evaluation/cases")
    assert resp.status_code == 404
