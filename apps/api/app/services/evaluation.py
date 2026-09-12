"""Evaluation harness (BRD Section 14): runs each EvaluationCase through the real retrieval
service and agent pipeline, and computes the required quality metrics from the stored results.

Metrics are derived at report time from raw per-result signals (retrieved_sources,
affected_files, evidence_chunk_ids, ...) rather than being pre-aggregated when a case runs, so
scoring logic can change without needing to re-run the (slow, LLM-backed) agent.
"""
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.change_request import ChangeRequest
from app.models.content_chunk import ContentChunk
from app.models.enums import AgentRunStatus, ChangeRequestStatus, EvaluationBehavior, EvaluationCategory
from app.models.evaluation import EvaluationCase, EvaluationResult
from app.models.generated_plan import GeneratedPlan
from app.services import agent_runner
from app.services.embeddings import embed_text
from app.services.retrieval import search_chunks


def _source_ref(chunk: ContentChunk, filename: str) -> str:
    return chunk.source_metadata.get("file_path") or filename


def _retrieved_sources(db: Session, project_id: uuid.UUID, query: str, limit: int = 8) -> list[str]:
    rows = search_chunks(db, project_id, embed_text(query), "all", limit=limit)
    seen: list[str] = []
    for chunk, filename, _score in rows:
        ref = _source_ref(chunk, filename)
        if ref not in seen:
            seen.append(ref)
    return seen


def _matches_any(expected: list[str], actual: list[str]) -> bool:
    """True if any expected substring appears (case-insensitively) in any actual string."""
    return any(any(exp.lower() in act.lower() for act in actual) for exp in expected)


def _grade(case: EvaluationCase, actual_behavior: EvaluationBehavior, retrieved: list[str]) -> tuple[bool, str]:
    if case.expected_behavior != actual_behavior:
        return False, f"expected {case.expected_behavior.value}, got {actual_behavior.value}"
    if case.expected_behavior == EvaluationBehavior.direct_answer and case.expected_sources:
        if not _matches_any(case.expected_sources, retrieved):
            return False, "none of the expected sources were retrieved"
    return True, "ok"


def _save_result(
    db: Session,
    case: EvaluationCase,
    *,
    run_id: uuid.UUID | None,
    actual_behavior: EvaluationBehavior,
    retrieved: list[str],
    affected_files: list[str],
    evidence_chunk_ids: list[str],
    confidence: str | None,
    latency_ms: int,
    notes: str,
    passed: bool = False,
) -> EvaluationResult:
    result = EvaluationResult(
        case_id=case.id,
        run_id=run_id,
        actual_behavior=actual_behavior,
        retrieved_sources=retrieved,
        affected_files=affected_files,
        evidence_chunk_ids=evidence_chunk_ids,
        confidence=confidence,
        passed=passed,
        notes=notes,
        latency_ms=latency_ms,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def run_case(db: Session, case: EvaluationCase, checkpointer, created_by: uuid.UUID, **graph_kwargs) -> EvaluationResult:
    retrieved = _retrieved_sources(db, case.project_id, case.request_text)

    change_request = ChangeRequest(
        project_id=case.project_id,
        created_by=created_by,
        request_text=case.request_text,
        status=ChangeRequestStatus.pending,
    )
    db.add(change_request)
    db.commit()
    db.refresh(change_request)

    started = time.monotonic()
    try:
        run = agent_runner.start_run(db, change_request, checkpointer, **graph_kwargs)
    except Exception:
        latency_ms = int((time.monotonic() - started) * 1000)
        return _save_result(
            db, case, run_id=None, actual_behavior=EvaluationBehavior.failed, retrieved=retrieved,
            affected_files=[], evidence_chunk_ids=[], confidence=None, latency_ms=latency_ms,
            notes="Agent run raised an exception.",
        )
    latency_ms = int((time.monotonic() - started) * 1000)

    affected_files: list[str] = []
    evidence_chunk_ids: list[str] = []
    confidence: str | None = None

    if run.status == AgentRunStatus.awaiting_clarification:
        actual_behavior = EvaluationBehavior.clarification
    elif run.status == AgentRunStatus.awaiting_approval:
        plan = (
            db.query(GeneratedPlan)
            .filter(GeneratedPlan.change_request_id == change_request.id)
            .order_by(GeneratedPlan.version.desc())
            .first()
        )
        content = plan.content if plan else {}
        affected_files = [f["file_path"] for f in content.get("affected_files", [])]
        evidence_chunk_ids = [e["chunk_id"] for e in content.get("evidence", [])]
        confidence = content.get("confidence")
        is_fallback = confidence == "low" and not content.get("evidence")
        actual_behavior = EvaluationBehavior.insufficient_evidence if is_fallback else EvaluationBehavior.direct_answer
    else:
        actual_behavior = EvaluationBehavior.failed

    passed, notes = _grade(case, actual_behavior, retrieved)
    return _save_result(
        db, case, run_id=run.id, actual_behavior=actual_behavior, retrieved=retrieved,
        affected_files=affected_files, evidence_chunk_ids=evidence_chunk_ids, confidence=confidence,
        latency_ms=latency_ms, notes=notes, passed=passed,
    )


def run_dataset(
    db: Session, project_id: uuid.UUID, checkpointer, created_by: uuid.UUID, **graph_kwargs
) -> list[EvaluationResult]:
    cases = db.query(EvaluationCase).filter(EvaluationCase.project_id == project_id).all()
    return [run_case(db, case, checkpointer, created_by, **graph_kwargs) for case in cases]


def _latest_result_per_case(db: Session, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, EvaluationResult]:
    if not case_ids:
        return {}
    results = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.case_id.in_(case_ids))
        .order_by(EvaluationResult.created_at.desc())
        .all()
    )
    latest: dict[uuid.UUID, EvaluationResult] = {}
    for r in results:
        latest.setdefault(r.case_id, r)
    return latest


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _reviewer_acceptance(db: Session, project_id: uuid.UUID) -> float | None:
    rows = (
        db.query(Approval.decision)
        .join(GeneratedPlan, GeneratedPlan.id == Approval.plan_id)
        .join(ChangeRequest, ChangeRequest.id == GeneratedPlan.change_request_id)
        .filter(ChangeRequest.project_id == project_id)
        .all()
    )
    decisions = [d.value for (d,) in rows if d.value != "regenerate_requested"]
    if not decisions:
        return None
    accepted = sum(1 for d in decisions if d in ("approved", "edit_approved"))
    return round(accepted / len(decisions), 4)


def compute_report(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    cases = db.query(EvaluationCase).filter(EvaluationCase.project_id == project_id).all()
    by_case = {c.id: c for c in cases}
    latest = _latest_result_per_case(db, list(by_case.keys()))

    direct_cases = [r for cid, r in latest.items() if by_case[cid].expected_behavior == EvaluationBehavior.direct_answer]
    retrieval_hits = [r for r in direct_cases if _matches_any(by_case[r.case_id].expected_sources, r.retrieved_sources)]
    retrieval_hit_rate = _safe_rate(len(retrieval_hits), len(direct_cases))

    precisions = []
    for cid, r in latest.items():
        expected = by_case[cid].expected_affected_files
        if not expected or not r.affected_files:
            continue
        relevant = sum(1 for f in r.affected_files if _matches_any(expected, [f]))
        precisions.append(relevant / len(r.affected_files))
    affected_file_precision = round(sum(precisions) / len(precisions), 4) if precisions else None

    all_citations: list[str] = []
    valid_citations: list[str] = []
    for r in latest.values():
        for cid_str in r.evidence_chunk_ids:
            all_citations.append(cid_str)
            try:
                exists = db.get(ContentChunk, uuid.UUID(cid_str)) is not None
            except ValueError:
                exists = False
            if exists:
                valid_citations.append(cid_str)
    citation_correctness = _safe_rate(len(valid_citations), len(all_citations))

    ambiguous_results = [r for cid, r in latest.items() if by_case[cid].category == EvaluationCategory.ambiguous]
    clarification_hits = [r for r in ambiguous_results if r.actual_behavior == EvaluationBehavior.clarification]
    clarification_accuracy = _safe_rate(len(clarification_hits), len(ambiguous_results))

    unsupported_claims = [
        r for r in latest.values()
        if r.actual_behavior == EvaluationBehavior.direct_answer
        and r.confidence in ("medium", "high")
        and not r.retrieved_sources
    ]
    unsupported_claim_rate = _safe_rate(len(unsupported_claims), len(latest)) if latest else None

    overall_pass_rate = _safe_rate(sum(1 for r in latest.values() if r.passed), len(latest)) if latest else None

    latencies = sorted(r.latency_ms for r in latest.values())
    median_latency = latencies[len(latencies) // 2] if latencies else None
    max_latency = latencies[-1] if latencies else None

    return {
        "total_cases": len(cases),
        "total_results": len(latest),
        "overall_pass_rate": overall_pass_rate,
        "retrieval_hit_rate": retrieval_hit_rate,
        "affected_file_precision": affected_file_precision,
        "citation_correctness": citation_correctness,
        "clarification_accuracy": clarification_accuracy,
        "unsupported_claim_rate": unsupported_claim_rate,
        "reviewer_acceptance": _reviewer_acceptance(db, project_id),
        "median_latency_ms": median_latency,
        "max_latency_ms": max_latency,
    }
