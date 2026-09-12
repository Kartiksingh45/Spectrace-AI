"""Bridges the LangGraph agent graph and our own DB tables.

The graph + its Postgres checkpointer own the low-level pause/resume mechanics; agent_runs /
agent_steps / generated_plans / change_requests stay the source of truth the API reads from, kept
in sync here after every invoke/resume rather than read directly from LangGraph's checkpoint
internals.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus, ApprovalDecision, ChangeRequestStatus
from app.models.generated_plan import GeneratedPlan


def _build_step_rows(messages: list) -> list[dict[str, Any]]:
    tool_calls: dict[str, tuple[str, dict]] = {}
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                tool_calls[tc["id"]] = (tc["name"], tc.get("args", {}))

    rows = []
    for m in messages:
        if isinstance(m, ToolMessage):
            name, args = tool_calls.get(m.tool_call_id, (m.name, {}))
            rows.append(
                {
                    "tool_name": name,
                    "input_summary": json.dumps(args)[:500],
                    "output_summary": str(m.content)[:500],
                    "status": "ok",
                }
            )
    return rows


def _sync_run_state(db: Session, run: AgentRun, change_request: ChangeRequest, result: dict[str, Any]) -> None:
    interrupts = result.get("__interrupt__")
    interrupt_info = interrupts[0].value if interrupts else None

    steps = []
    if result.get("request_type"):
        steps.append(
            {
                "tool_name": None,
                "input_summary": change_request.request_text[:500],
                "output_summary": f"Classified as {result['request_type']}",
                "status": "ok",
            }
        )
    steps.extend(_build_step_rows(result.get("messages", [])))

    db.query(AgentStep).filter(AgentStep.run_id == run.id).delete()
    for i, row in enumerate(steps):
        db.add(AgentStep(run_id=run.id, step_index=i, duration_ms=0, **row))

    if interrupt_info and interrupt_info["type"] == "clarification":
        run.status = AgentRunStatus.awaiting_clarification
        change_request.status = ChangeRequestStatus.awaiting_clarification
        db.add(
            AgentStep(
                run_id=run.id,
                step_index=len(steps),
                tool_name="request_clarification",
                input_summary=interrupt_info["question"],
                output_summary="(awaiting answer)",
                duration_ms=0,
            )
        )
    elif interrupt_info and interrupt_info["type"] == "approval":
        run.status = AgentRunStatus.awaiting_approval
        change_request.status = ChangeRequestStatus.awaiting_approval
        existing = db.query(GeneratedPlan).filter(GeneratedPlan.change_request_id == change_request.id).count()
        db.add(
            GeneratedPlan(
                change_request_id=change_request.id,
                run_id=run.id,
                version=existing + 1,
                content=result["generated_plan"],
            )
        )
    else:
        run.status = AgentRunStatus.completed
        run.ended_at = datetime.now(timezone.utc)
        final_decision = result.get("final_decision") or {}
        decision = final_decision.get("decision")
        if decision in (ApprovalDecision.approved.value, ApprovalDecision.edit_approved.value):
            change_request.status = ChangeRequestStatus.approved
        elif decision == ApprovalDecision.rejected.value:
            change_request.status = ChangeRequestStatus.rejected
        else:
            change_request.status = ChangeRequestStatus.failed

    if change_request.request_type is None and result.get("request_type"):
        change_request.request_type = result["request_type"]

    db.commit()


def start_run(db: Session, change_request: ChangeRequest, checkpointer, **graph_kwargs) -> AgentRun:
    thread_id = str(uuid.uuid4())
    run = AgentRun(change_request_id=change_request.id, thread_id=thread_id, status=AgentRunStatus.running)
    db.add(run)
    change_request.status = ChangeRequestStatus.analysing
    db.commit()
    db.refresh(run)

    graph = build_graph(db, change_request.project_id, checkpointer, **graph_kwargs)
    initial_state = {
        "messages": [],
        "request_text": change_request.request_text,
        "request_type": None,
        "evidence": [],
        "generated_plan": None,
        "generated_plan_valid": False,
        "review_retries": 0,
        "step_count": 0,
        "final_decision": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(initial_state, config)

    _sync_run_state(db, run, change_request, result)
    return run


def resume_clarification(
    db: Session, run: AgentRun, change_request: ChangeRequest, answer: str, checkpointer, **graph_kwargs
) -> AgentRun:
    graph = build_graph(db, change_request.project_id, checkpointer, **graph_kwargs)
    config = {"configurable": {"thread_id": run.thread_id}}
    result = graph.invoke(Command(resume=answer), config)
    _sync_run_state(db, run, change_request, result)
    return run


def resume_decision(
    db: Session,
    run: AgentRun,
    change_request: ChangeRequest,
    decision: dict[str, Any],
    checkpointer,
    **graph_kwargs,
) -> AgentRun:
    graph = build_graph(db, change_request.project_id, checkpointer, **graph_kwargs)
    config = {"configurable": {"thread_id": run.thread_id}}
    result = graph.invoke(Command(resume=decision), config)
    _sync_run_state(db, run, change_request, result)
    return run
