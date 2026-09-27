import io

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


def test_document_upload_records_ingestion_duration(client):
    client.post("/auth/register", json={"email": "obs@example.com", "password": "hunter2pass"})
    project = client.post("/projects", json={"name": "Demo"}).json()

    content = b"Mobile OTP must be verified before loan submission. " * 20
    started = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": ("rules.txt", io.BytesIO(content), "text/plain")},
    ).json()
    # Embedding now runs as a background task - its own response reflects the state from just
    # before that task ran, so re-fetch for the up-to-date state.
    docs = client.get(f"/projects/{project['id']}/documents").json()
    upload = next(d for d in docs if d["id"] == started["id"])

    assert upload["status"] == "ready"
    assert isinstance(upload["duration_ms"], int)
    assert upload["duration_ms"] >= 0


def test_run_and_steps_record_duration(client):
    client.post("/auth/register", json={"email": "obs2@example.com", "password": "hunter2pass"})
    project = client.post("/projects", json={"name": "Demo"}).json()

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
        # analyse now runs the agent turn as a background task - its own response reflects the
        # state from just before that task ran, so re-fetch for the up-to-date state.
        run = client.get(f"/runs/{started['id']}").json()
    finally:
        app.dependency_overrides.pop(get_checkpointer, None)
        app.dependency_overrides.pop(get_agent_overrides, None)

    assert run["status"] == "awaiting_approval"
    assert run["started_at"] is not None
    assert run["ended_at"] is None  # still open - awaiting a reviewer decision
    assert run["duration_ms"] is None

    for step in run["steps"]:
        assert isinstance(step["duration_ms"], int)
        assert step["duration_ms"] >= 0
