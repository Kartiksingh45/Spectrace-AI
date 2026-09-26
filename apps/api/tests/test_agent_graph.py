import uuid

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent.graph import _fallback_plan, build_graph
from app.agent.schemas import EvidenceRef, GeneratedPlan


class ScriptedModel(FakeMessagesListChatModel):
    """A fake chat model whose scripted responses drive the agent's tool-calling decisions.

    bind_tools is stubbed to a no-op: we pre-script the exact AIMessage (including tool_calls) the
    "model" returns at each turn, so there's nothing for real tool-binding to add.
    """

    def bind_tools(self, tools, **kwargs):
        return self


def _gemini_client_error():
    from google.genai.errors import ClientError as GeminiClientError

    return GeminiClientError(400, {"error": {"message": "tool call validation failed"}}, None)


class RaisingModel(FakeMessagesListChatModel):
    """Simulates the provider hard-rejecting a hallucinated tool call (a real failure mode seen
    with some hosted models) instead of returning a normal response."""

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        raise _gemini_client_error()


def _tool_call(name: str, args: dict | None = None, call_id: str = "1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])


def _plan(confidence="low", evidence=None, affected_files=None) -> GeneratedPlan:
    return GeneratedPlan(
        summary="summary",
        request_type="feature",
        questions=[],
        evidence=evidence or [],
        affected_files=affected_files or [],
        user_story="As a user...",
        acceptance_criteria=["works"],
        tasks=[],
        test_cases=[],
        confidence=confidence,
    )


def _initial_state(request_text: str = "Add mobile OTP verification") -> dict:
    return {
        "messages": [],
        "request_text": request_text,
        "request_type": None,
        "evidence": [],
        "generated_plan": None,
        "generated_plan_valid": False,
        "review_retries": 0,
        "step_count": 0,
        "final_decision": None,
    }


def _build(responses, plan_generator, db=None, project_id=None):
    graph = build_graph(
        db or object(),
        project_id or uuid.uuid4(),
        InMemorySaver(),
        agent_model=ScriptedModel(responses=responses),
        classifier=lambda text: "feature",
        plan_generator=plan_generator,
    )
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    return graph, config


def test_generate_plan_reaches_awaiting_approval():
    graph, config = _build(
        responses=[_tool_call("generate_plan")],
        plan_generator=lambda *a: _plan(),
    )
    result = graph.invoke(_initial_state(), config)

    assert result["__interrupt__"][0].value["type"] == "approval"
    assert result["generated_plan"]["summary"] == "summary"


def test_request_clarification_pauses_and_resumes():
    graph, config = _build(
        responses=[
            _tool_call("request_clarification", {"question": "When should OTP trigger?"}),
            _tool_call("generate_plan"),
        ],
        plan_generator=lambda *a: _plan(),
    )
    first = graph.invoke(_initial_state(), config)
    assert first["__interrupt__"][0].value == {"type": "clarification", "question": "When should OTP trigger?"}

    second = graph.invoke(Command(resume="Trigger before final submit."), config)
    assert second["__interrupt__"][0].value["type"] == "approval"


def test_fabricated_citation_is_bounced_back_then_corrected():
    calls = {"n": 0}

    def plan_generator(request_text, request_type, evidence, feedback):
        calls["n"] += 1
        if calls["n"] == 1:
            return _plan(evidence=[EvidenceRef(chunk_id="not-a-real-chunk", note="x")])
        assert feedback and "not-a-real-chunk" in feedback
        return _plan(confidence="medium")

    graph, config = _build(
        responses=[_tool_call("generate_plan", call_id="1"), _tool_call("generate_plan", call_id="2")],
        plan_generator=plan_generator,
    )
    result = graph.invoke(_initial_state(), config)

    assert calls["n"] == 2
    assert result["generated_plan"]["confidence"] == "medium"
    assert result["__interrupt__"][0].value["type"] == "approval"


def test_step_cap_forces_insufficient_evidence_fallback():
    # The model just keeps asking pointless clarifying questions and never calls generate_plan.
    responses = [_tool_call("request_clarification", {"question": f"q{i}"}, call_id=str(i)) for i in range(20)]
    graph, config = _build(responses=responses, plan_generator=lambda *a: pytest.fail("should not be called"))

    result = graph.invoke(_initial_state(), config)
    # Each clarification pauses; answer every one until the step cap kicks in and forces a fallback.
    for _ in range(20):
        if result.get("__interrupt__") is None:
            break
        if result["__interrupt__"][0].value["type"] == "approval":
            break
        result = graph.invoke(Command(resume="keep going"), config)

    assert result["generated_plan"]["confidence"] == "low"
    assert "Insufficient evidence" in result["generated_plan"]["summary"]


def test_fallback_plan_surfaces_accumulated_evidence_as_low_confidence_leads():
    # The agent found real (if unconfirmed) leads before running out of budget - the fallback
    # should surface them as low-confidence candidates rather than discarding everything.
    evidence = [
        {"chunk_id": "c1", "content_type": "code", "reference": "src/Login.tsx", "score": 0.34},
        {"chunk_id": "c1", "content_type": "code", "reference": "src/Login.tsx", "score": 0.34},  # dup
        {"chunk_id": "c2", "content_type": "code", "reference": "src/Signup.tsx", "score": 0.31},
        {"chunk_id": "c3", "content_type": "requirement", "reference": "spec.md", "score": 0.28},
    ]

    plan = _fallback_plan("add captcha on sign in", "feature", evidence)

    assert plan.confidence == "low"
    assert {f.file_path for f in plan.affected_files} == {"src/Login.tsx", "src/Signup.tsx"}
    assert all(f.confidence == "low" for f in plan.affected_files)
    assert {e.chunk_id for e in plan.evidence} == {"c1", "c2", "c3"}  # deduplicated


def test_fallback_plan_with_no_evidence_stays_empty():
    plan = _fallback_plan("add captcha on sign in", "feature", [])

    assert plan.affected_files == []
    assert plan.evidence == []
    assert "unconfirmed leads" not in plan.summary


def test_provider_rejected_tool_call_falls_back_instead_of_crashing():
    # Simulates the model hallucinating a tool name outside our schema - the provider hard-rejects
    # that with a 4xx rather than returning a normal message. The run should still resolve to a
    # (low-confidence) plan for reviewer approval, not propagate the provider error.
    graph = build_graph(
        object(),
        uuid.uuid4(),
        InMemorySaver(),
        agent_model=RaisingModel(responses=[]),
        classifier=lambda text: "feature",
        plan_generator=lambda *a: pytest.fail("should not be called"),
    )
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke(_initial_state(), config)

    assert result["__interrupt__"][0].value["type"] == "approval"
    assert result["generated_plan"]["confidence"] == "low"


def test_approve_decision_ends_run_without_further_interrupt():
    graph, config = _build(responses=[_tool_call("generate_plan")], plan_generator=lambda *a: _plan())
    graph.invoke(_initial_state(), config)

    result = graph.invoke(Command(resume={"decision": "approved", "feedback": None}), config)

    assert result.get("__interrupt__") is None
    assert result["final_decision"]["decision"] == "approved"


def test_regenerate_decision_loops_back_for_a_new_version():
    calls = {"n": 0}

    def plan_generator(request_text, request_type, evidence, feedback):
        calls["n"] += 1
        return _plan(confidence="low" if calls["n"] == 1 else "high")

    graph, config = _build(
        responses=[_tool_call("generate_plan", call_id="1"), _tool_call("generate_plan", call_id="2")],
        plan_generator=plan_generator,
    )
    graph.invoke(_initial_state(), config)

    result = graph.invoke(Command(resume={"decision": "regenerate_requested", "feedback": "add more detail"}), config)

    assert calls["n"] == 2
    assert result["generated_plan"]["confidence"] == "high"
    assert result["__interrupt__"][0].value["type"] == "approval"
