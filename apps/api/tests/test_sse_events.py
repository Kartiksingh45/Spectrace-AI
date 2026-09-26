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


def _parse_sse(raw: str) -> list[dict]:
    """Minimal SSE parser good enough for this endpoint's own output: splits on blank lines,
    reads the `data:` (and optional `event:`) fields of each block."""
    events = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        fields = {}
        for line in block.splitlines():
            if ": " in line:
                key, _, value = line.partition(": ")
                fields[key] = value
        events.append(fields)
    return events


def test_stream_events_replays_history_and_ends_with_done_for_a_finished_run(client):
    client.post("/auth/register", json={"email": "sse@example.com", "password": "hunter2pass"})
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
        run = client.post(f"/requests/{change_request['id']}/analyse").json()
        assert run["status"] == "awaiting_approval"

        with client.stream("GET", f"/requests/{change_request['id']}/events") as response:
            assert response.status_code == 200
            raw = "".join(response.iter_text())
    finally:
        app.dependency_overrides.pop(get_checkpointer, None)
        app.dependency_overrides.pop(get_agent_overrides, None)

    events = _parse_sse(raw)
    assert events[-1]["event"] == "done"
    assert events[-1]["data"] == '{"status": "awaiting_approval"}'
    # Every step already persisted by the (already-finished) analyse call was replayed.
    step_events = [e for e in events if "event" not in e]
    assert any('"tool_name": "generate_plan"' in e["data"] for e in step_events)


def test_stream_events_requires_membership(client):
    client.post("/auth/register", json={"email": "owner@example.com", "password": "hunter2pass"})
    project = client.post("/projects", json={"name": "Demo"}).json()
    change_request = client.post(
        f"/projects/{project['id']}/requests", json={"request_text": "Add mobile OTP"}
    ).json()
    client.post("/auth/logout")

    client.post("/auth/register", json={"email": "intruder@example.com", "password": "hunter2pass"})
    with client.stream("GET", f"/requests/{change_request['id']}/events") as response:
        assert response.status_code == 404
