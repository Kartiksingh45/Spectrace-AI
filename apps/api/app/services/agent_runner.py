"""Bridges the LangGraph agent graph and our own DB tables.

The graph + its Postgres checkpointer own the low-level pause/resume mechanics; agent_runs /
agent_steps / generated_plans / change_requests stay the source of truth the API reads from, kept
in sync here after every invoke/resume rather than read directly from LangGraph's checkpoint
internals.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus, ApprovalDecision, ChangeRequestStatus
from app.models.generated_plan import GeneratedPlan

logger = logging.getLogger(__name__)


class ToolTimingCallback(BaseCallbackHandler):
    """Records how long each tool call took, in the order the tools were invoked - the same
    order _build_step_rows later reconstructs from the resulting ToolMessages, so the two lists
    line up positionally. Without this every step was persisted with a hardcoded duration_ms=0.
    """

    def __init__(self) -> None:
        self.durations_ms: list[int] = []
        self._starts: dict[str, float] = {}

    def on_tool_start(self, serialized: dict, input_str: str, *, run_id, **kwargs: Any) -> None:
        self._starts[str(run_id)] = time.monotonic()

    def _finish(self, run_id) -> None:
        start = self._starts.pop(str(run_id), None)
        if start is not None:
            self.durations_ms.append(int((time.monotonic() - start) * 1000))

    def on_tool_end(self, output: Any, *, run_id, **kwargs: Any) -> None:
        self._finish(run_id)

    def on_tool_error(self, error: BaseException, *, run_id, **kwargs: Any) -> None:
        self._finish(run_id)


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


def _merge_step_durations(
    existing: list[AgentStep], steps: list[dict[str, Any]], fresh_durations: list[int], preserve_up_to: int
) -> list[dict[str, Any]]:
    """`steps` is rebuilt from scratch (from the full, ever-growing message history) on every
    resume, so step_index N does not reliably mean "the same tool call" across resumes - e.g. a
    clarification's placeholder step disappears once answered. Reuse the previously recorded
    duration only for indexes below `preserve_up_to` (steps that already existed before THIS
    invoke started, from an earlier resume) whose content still matches what was persisted before;
    every index at or above `preserve_up_to` is this invoke's own work and always gets timed for
    real from its ToolTimingCallback, in order - even though live SSE streaming
    (`_persist_partial_steps`) may have already inserted placeholder rows for them mid-run with a
    duration_ms of 0, which must not be mistaken for their real, now-known duration.
    """
    fresh_iter = iter(fresh_durations)
    merged = []
    for i, row in enumerate(steps):
        old = existing[i] if i < len(existing) else None
        if (
            i < preserve_up_to
            and old is not None
            and old.tool_name == row["tool_name"]
            and old.input_summary == row["input_summary"]
            and old.output_summary == row["output_summary"]
        ):
            duration = old.duration_ms
        else:
            duration = next(fresh_iter, 0)
        merged.append({**row, "duration_ms": duration})
    return merged


def _steps_from_state(change_request_text: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    steps = []
    if state.get("request_type"):
        steps.append(
            {
                "tool_name": None,
                "input_summary": change_request_text[:500],
                "output_summary": f"Classified as {state['request_type']}",
                "status": "ok",
            }
        )
    steps.extend(_build_step_rows(state.get("messages", [])))
    return steps


def _persist_partial_steps(db: Session, run: AgentRun, change_request_text: str, state: dict[str, Any]) -> None:
    """Called after each super-step while the graph is still streaming (`_invoke_and_sync`), so a
    concurrent `GET /runs/{id}/events` reader can show steps as they actually happen instead of
    all at once at the end. Only ever appends - `_sync_run_state` is still what reconciles the
    final, authoritative set of rows (with real durations) once the invoke finishes or pauses.
    """
    steps = _steps_from_state(change_request_text, state)
    existing_count = db.query(AgentStep).filter(AgentStep.run_id == run.id).count()
    if len(steps) <= existing_count:
        return
    for i, row in enumerate(steps[existing_count:], start=existing_count):
        db.add(AgentStep(run_id=run.id, step_index=i, duration_ms=0, **row))
    db.commit()


def _sync_run_state(
    db: Session,
    run: AgentRun,
    change_request: ChangeRequest,
    result: dict[str, Any],
    tool_durations: list[int] | None = None,
    preserve_up_to: int = 0,
) -> None:
    interrupts = result.get("__interrupt__")
    interrupt_info = interrupts[0].value if interrupts else None

    steps = _steps_from_state(change_request.request_text, result)

    existing = db.query(AgentStep).filter(AgentStep.run_id == run.id).order_by(AgentStep.step_index.asc()).all()
    steps = _merge_step_durations(existing, steps, tool_durations or [], preserve_up_to)

    db.query(AgentStep).filter(AgentStep.run_id == run.id).delete()
    for i, row in enumerate(steps):
        db.add(AgentStep(run_id=run.id, step_index=i, **row))
        logger.info(
            "agent_step run_id=%s step_index=%s tool=%s status=%s duration_ms=%s",
            run.id, i, row["tool_name"], row["status"], row["duration_ms"],
        )

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


def _invoke_and_sync(
    db: Session, run: AgentRun, change_request: ChangeRequest, graph, graph_input, config: dict
) -> AgentRun:
    """Run the graph and sync state, leaving the run/change_request cleanly marked `failed`
    (rather than stuck at `running` forever) if the invocation raises - e.g. a model/API error.
    Without this, a mid-flight exception left no record of failure, and analyse's idempotency
    check would then mistake the stale `running` status for an in-flight run and silently no-op
    on retry instead of surfacing (or letting the user retry) the failure.
    """
    timing = ToolTimingCallback()
    config = {**config, "callbacks": [*config.get("callbacks", []), timing]}
    invoke_started = time.monotonic()
    steps_before = db.query(AgentStep).filter(AgentStep.run_id == run.id).count()
    result: dict[str, Any] = {}
    try:
        # stream() rather than invoke() so each super-step's new tool-call result is persisted as
        # it happens (`_persist_partial_steps`), not only once the whole run finishes - that's
        # what lets `GET /runs/{id}/events` show genuinely live progress rather than everything
        # arriving in one burst at the end. The final `result` (the last yielded state) is exactly
        # what `graph.invoke()` itself would have returned, interrupts included.
        for state in graph.stream(graph_input, config, stream_mode="values"):
            result = state
            _persist_partial_steps(db, run, change_request.request_text, state)
    except Exception:
        db.rollback()
        duration_ms = int((time.monotonic() - invoke_started) * 1000)
        logger.exception(
            "agent_run_failed run_id=%s duration_ms=%s", run.id, duration_ms
        )
        run.status = AgentRunStatus.failed
        run.ended_at = datetime.now(timezone.utc)
        change_request.status = ChangeRequestStatus.failed
        db.commit()
        raise
    duration_ms = int((time.monotonic() - invoke_started) * 1000)
    _sync_run_state(db, run, change_request, result, timing.durations_ms, preserve_up_to=steps_before)
    logger.info(
        "agent_run_invoke_finished run_id=%s status=%s duration_ms=%s", run.id, run.status.value, duration_ms
    )
    return run


def start_run(db: Session, change_request: ChangeRequest, checkpointer, **graph_kwargs) -> AgentRun:
    """Creates the run row and returns immediately - the graph itself is NOT executed here.
    Callers that need the run to actually happen must follow this with `execute_run` (directly,
    for a synchronous caller like a test, or scheduled as a FastAPI BackgroundTask so the
    triggering HTTP request doesn't block for the run's full duration - which can exceed a host's
    proxy timeout, e.g. Render's ~60s limit, for a run that legitimately takes over a minute).
    """
    thread_id = str(uuid.uuid4())
    run = AgentRun(change_request_id=change_request.id, thread_id=thread_id, status=AgentRunStatus.running)
    db.add(run)
    change_request.status = ChangeRequestStatus.analysing
    db.commit()
    db.refresh(run)
    logger.info("agent_run_started run_id=%s change_request_id=%s", run.id, change_request.id)
    return run


def execute_run(db: Session, run: AgentRun, change_request: ChangeRequest, checkpointer, **graph_kwargs) -> AgentRun:
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
    config = {"configurable": {"thread_id": run.thread_id}}
    return _invoke_and_sync(db, run, change_request, graph, initial_state, config)


def prepare_resume(db: Session, run: AgentRun) -> None:
    """Flips the run back to `running` immediately, before the (potentially slow) actual resume
    is scheduled as a background task - gives a poller something to see right away rather than
    the run appearing stuck at its old paused status until the background task finishes."""
    run.status = AgentRunStatus.running
    db.commit()


def execute_resume_clarification(
    db: Session, run: AgentRun, change_request: ChangeRequest, answer: str, checkpointer, **graph_kwargs
) -> AgentRun:
    graph = build_graph(db, change_request.project_id, checkpointer, **graph_kwargs)
    config = {"configurable": {"thread_id": run.thread_id}}
    return _invoke_and_sync(db, run, change_request, graph, Command(resume=answer), config)


def execute_resume_decision(
    db: Session,
    run: AgentRun,
    change_request: ChangeRequest,
    decision: dict[str, Any],
    checkpointer,
    **graph_kwargs,
) -> AgentRun:
    graph = build_graph(db, change_request.project_id, checkpointer, **graph_kwargs)
    config = {"configurable": {"thread_id": run.thread_id}}
    return _invoke_and_sync(db, run, change_request, graph, Command(resume=decision), config)
