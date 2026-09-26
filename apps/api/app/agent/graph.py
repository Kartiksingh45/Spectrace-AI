"""The Spectrace AI agent graph: classify -> agent (tool-calling loop) -> review -> await_approval.

Fixed skeleton per BRD 7.2; the agent chooses which tool to call at each step within it. Grounding
is enforced deterministically in `review` (not trusted to the model's judgement): every evidence
chunk_id and affected-file path the model cites in its plan must have actually been returned by a
search tool during this run.
"""
import logging
import uuid
from typing import Any, Callable

from google.genai.errors import ClientError as GeminiClientError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from sqlalchemy.orm import Session

from app.agent.llm import classify_request, generate_plan_with_llm
from app.agent.schemas import AffectedFile, EvidenceRef, GeneratedPlan
from app.agent.state import AgentState, EvidenceItem
from app.agent.tools import build_tools
from app.core.config import settings

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are Spectrace AI's change-impact analysis agent. A request has been \
classified as: {request_type}.

Use the available tools to gather evidence before proposing anything:
- search_requirements / search_codebase: find relevant requirement text and code.
- get_file_context: see more of a promising chunk you already found (pass its chunk_id).
- find_similar_stories: check how similar past requests were handled.
- request_clarification: ask the user a specific question ONLY if information required to proceed \
is genuinely missing - do not ask about things you could instead search for.
- generate_plan: call this once you have gathered enough evidence to responsibly propose a plan. \
You may only cite chunk_ids and file paths that actually appeared in your tool results.

You have a HARD LIMIT of {max_steps} tool calls total this run - this call is tool call number \
{call_number} of {max_steps}. Do not re-run near-duplicate searches (e.g. the same concept with a \
slightly reworded query) hoping for a better match - a search you already ran will not return \
better results the second time. {budget_instruction} Call exactly one tool per turn."""


def _grounding_errors(plan: dict[str, Any], evidence: list[dict[str, Any]]) -> list[str]:
    chunk_ids = {e["chunk_id"] for e in evidence}
    file_refs = {e["reference"] for e in evidence if e["content_type"] == "code"}

    errors = []
    for ref in plan.get("evidence", []):
        if ref["chunk_id"] not in chunk_ids:
            errors.append(f"evidence cites unknown chunk_id {ref['chunk_id']}")
    for f in plan.get("affected_files", []):
        if f["file_path"] not in file_refs:
            errors.append(f"affected_files cites file_path {f['file_path']!r} not seen in this run's code search results")
    return errors


def _fallback_plan(
    request_text: str, request_type: str | None, evidence: list[EvidenceItem]
) -> GeneratedPlan:
    """Built when the agent never reached a reviewer-ready plan (ran out of steps, or repeatedly
    failed grounding). Still surfaces whatever the search tools actually turned up during the run
    - even weak, unconfirmed leads - as low-confidence candidates, rather than discarding real
    search results just because the model didn't commit to a full plan around them. For a user
    whose whole goal is "where do I even start looking in this codebase", an unconfirmed lead is
    far more useful than nothing.
    """
    seen_chunks: set[str] = set()
    evidence_refs: list[EvidenceRef] = []
    seen_files: set[str] = set()
    affected_files: list[AffectedFile] = []
    for item in evidence:
        if item["chunk_id"] not in seen_chunks:
            seen_chunks.add(item["chunk_id"])
            evidence_refs.append(
                EvidenceRef(
                    chunk_id=item["chunk_id"],
                    note=f"Turned up during search (score {item['score']:.2f}) - relevance not confirmed.",
                )
            )
        if item["content_type"] == "code" and item["reference"] not in seen_files:
            seen_files.add(item["reference"])
            affected_files.append(
                AffectedFile(
                    file_path=item["reference"],
                    reason="Surfaced by search for this request; the agent could not confirm direct relevance - review manually.",
                    confidence="low",
                )
            )

    summary = f"Insufficient evidence was found to responsibly analyse: {request_text}"
    if affected_files or evidence_refs:
        summary += " A few unconfirmed leads turned up during search - see affected files and evidence below."

    return GeneratedPlan(
        summary=summary,
        request_type=request_type or "feature",
        questions=[],
        evidence=evidence_refs,
        affected_files=affected_files,
        user_story="Not enough grounded evidence was available to propose a user story.",
        acceptance_criteria=[],
        tasks=[],
        test_cases=[],
        assumptions=["This is a fallback response - a reviewer should investigate manually."],
        risks=["Generated without sufficiently grounded evidence."],
        confidence="low",
    )


def build_graph(
    db: Session,
    project_id: uuid.UUID,
    checkpointer,
    agent_model: BaseChatModel | None = None,
    classifier: Callable[[str], str] | None = None,
    plan_generator: Callable[[str, str | None, list[dict], str | None], GeneratedPlan] | None = None,
):
    classifier = classifier or classify_request
    plan_generator = plan_generator or generate_plan_with_llm

    if agent_model is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        agent_model = ChatGoogleGenerativeAI(
            model=settings.gemini_model_name,
            google_api_key=settings.gemini_api_key,
            temperature=0,
            timeout=settings.gemini_request_timeout_seconds,
        )

    tools = build_tools(db, project_id, plan_generator)
    model_with_tools = agent_model.bind_tools(tools)

    def classify_node(state: AgentState) -> dict:
        return {"request_type": classifier(state["request_text"])}

    def agent_node(state: AgentState) -> dict:
        call_number = state.get("step_count", 0) + 1
        remaining_after_this = settings.agent_max_steps - call_number
        if remaining_after_this <= 0:
            budget_instruction = (
                "This is your LAST allowed tool call - you MUST call generate_plan now with "
                "whatever evidence you have gathered, even if it feels incomplete."
            )
        elif remaining_after_this <= 2:
            budget_instruction = (
                f"Only {remaining_after_this} tool call(s) remain after this one - call generate_plan "
                "now unless you are still missing evidence for a core part of the request."
            )
        else:
            budget_instruction = (
                "If you already have at least one relevant requirement chunk and one relevant code "
                "chunk, call generate_plan now rather than continuing to search."
            )
        system = SystemMessage(
            AGENT_SYSTEM_PROMPT.format(
                request_type=state.get("request_type"),
                max_steps=settings.agent_max_steps,
                call_number=call_number,
                budget_instruction=budget_instruction,
            )
        )
        def invoke(messages: list) -> AIMessage:
            try:
                return model_with_tools.invoke(messages)
            except GeminiClientError as exc:
                # The model can occasionally emit a tool call outside the schema we gave it (e.g. a
                # hallucinated tool name); the provider hard-rejects that server-side with a 4xx
                # instead of returning a normal message. Treat it as "no valid tool call this turn"
                # rather than crashing the whole run - route_after_agent falls through to
                # insufficient_evidence, which still surfaces whatever real evidence was gathered
                # earlier in the run.
                logger.warning("Model tool call rejected by provider, treating as no tool call: %s", exc)
                return AIMessage(content="(The model's last response could not be used.)")

        if not state["messages"]:
            first = HumanMessage(state["request_text"])
            response = invoke([system, first])
            return {"messages": [first, response], "step_count": state.get("step_count", 0) + 1}
        response = invoke([system] + state["messages"])
        return {"messages": [response], "step_count": state.get("step_count", 0) + 1}

    def review_node(state: AgentState) -> dict:
        errors = _grounding_errors(state["generated_plan"], state["evidence"])
        if not errors:
            return {"generated_plan_valid": True}
        retries = state.get("review_retries", 0) + 1
        correction = HumanMessage(
            "Your generated plan failed grounding review: " + "; ".join(errors) + ". Call generate_plan again."
        )
        return {"messages": [correction], "review_retries": retries, "generated_plan_valid": False}

    def insufficient_evidence_node(state: AgentState) -> dict:
        plan = _fallback_plan(state["request_text"], state.get("request_type"), state.get("evidence", []))
        return {"generated_plan": plan.model_dump(), "generated_plan_valid": True}

    def await_approval_node(state: AgentState) -> dict:
        decision = interrupt({"type": "approval", "plan": state["generated_plan"]})
        if decision.get("decision") == "regenerate_requested":
            note = HumanMessage(f"Reviewer requested changes: {decision.get('feedback') or '(no detail given)'}")
            return {"messages": [note], "generated_plan": None, "generated_plan_valid": False, "review_retries": 0}
        return {"final_decision": decision}

    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "insufficient_evidence"

    def route_after_tools(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "name", None) == "generate_plan":
            return "review"
        if state.get("step_count", 0) >= settings.agent_max_steps:
            return "insufficient_evidence"
        return "agent"

    def route_after_review(state: AgentState) -> str:
        if state.get("generated_plan_valid"):
            return "await_approval"
        if state.get("review_retries", 0) > settings.agent_review_max_retries:
            return "insufficient_evidence"
        return "agent"

    def route_after_await_approval(state: AgentState) -> str:
        if state.get("final_decision"):
            return END
        return "agent"

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("review", review_node)
    graph.add_node("insufficient_evidence", insufficient_evidence_node)
    graph.add_node("await_approval", await_approval_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "agent")
    graph.add_conditional_edges("agent", route_after_agent, ["tools", "insufficient_evidence"])
    graph.add_conditional_edges("tools", route_after_tools, ["review", "agent", "insufficient_evidence"])
    graph.add_conditional_edges("review", route_after_review, ["await_approval", "agent", "insufficient_evidence"])
    graph.add_edge("insufficient_evidence", "await_approval")
    graph.add_conditional_edges("await_approval", route_after_await_approval, ["agent", END])

    return graph.compile(checkpointer=checkpointer)
