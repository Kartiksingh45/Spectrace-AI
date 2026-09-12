import uuid
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.schemas import GeneratedPlan
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind, DocumentStatus, EvaluationBehavior, EvaluationCategory
from app.models.evaluation import EvaluationCase, EvaluationResult
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services.evaluation import compute_report, run_case, run_dataset


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


def _make_project(db_session) -> tuple[User, Project]:
    user = User(email="evaluator@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    project = Project(name="Eval Project", owner_id=user.id)
    db_session.add(project)
    db_session.flush()
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id))
    db_session.commit()
    return user, project


def _make_case(db_session, project, **overrides) -> EvaluationCase:
    base = dict(
        project_id=project.id,
        title="case",
        request_text="Do the thing",
        category=EvaluationCategory.clear,
        expected_behavior=EvaluationBehavior.direct_answer,
        expected_sources=[],
        expected_affected_files=[],
    )
    base.update(overrides)
    case = EvaluationCase(**base)
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


# --- run_case: drives the real graph (search tools untouched - covered separately, matching the
# project's existing precedent of not exercising pgvector-backed search against SQLite) ---


def test_run_case_direct_answer_hit_marks_case_passed(db_session):
    user, project = _make_project(db_session)
    case = _make_case(
        db_session, project,
        category=EvaluationCategory.clear,
        expected_behavior=EvaluationBehavior.direct_answer,
        expected_sources=["src/otp.py"],
    )
    checkpointer = InMemorySaver()
    with patch("app.services.evaluation._retrieved_sources", return_value=["src/otp.py"]):
        result = run_case(
            db_session, case, checkpointer, created_by=user.id,
            agent_model=ScriptedModel(responses=[_tool_call("generate_plan")]),
            classifier=lambda text: "feature",
            plan_generator=lambda *a: _plan(confidence="high"),
        )

    assert result.actual_behavior == EvaluationBehavior.direct_answer
    assert result.passed is True
    assert result.retrieved_sources == ["src/otp.py"]


def test_run_case_direct_answer_miss_marks_case_failed(db_session):
    user, project = _make_project(db_session)
    case = _make_case(
        db_session, project,
        expected_behavior=EvaluationBehavior.direct_answer,
        expected_sources=["src/otp.py"],
    )
    checkpointer = InMemorySaver()
    with patch("app.services.evaluation._retrieved_sources", return_value=["src/unrelated.py"]):
        result = run_case(
            db_session, case, checkpointer, created_by=user.id,
            agent_model=ScriptedModel(responses=[_tool_call("generate_plan")]),
            classifier=lambda text: "feature",
            plan_generator=lambda *a: _plan(confidence="high"),
        )

    assert result.passed is False
    assert "expected sources" in result.notes


def test_run_case_ambiguous_case_expecting_clarification(db_session):
    user, project = _make_project(db_session)
    case = _make_case(
        db_session, project,
        category=EvaluationCategory.ambiguous,
        expected_behavior=EvaluationBehavior.clarification,
    )
    checkpointer = InMemorySaver()
    with patch("app.services.evaluation._retrieved_sources", return_value=[]):
        result = run_case(
            db_session, case, checkpointer, created_by=user.id,
            agent_model=ScriptedModel(responses=[_tool_call("request_clarification", {"question": "when?"})]),
            classifier=lambda text: "feature",
            plan_generator=lambda *a: _plan(),
        )

    assert result.actual_behavior == EvaluationBehavior.clarification
    assert result.passed is True


def test_run_case_unsupported_case_detects_fallback_plan(db_session):
    user, project = _make_project(db_session)
    case = _make_case(
        db_session, project,
        category=EvaluationCategory.unsupported,
        expected_behavior=EvaluationBehavior.insufficient_evidence,
    )
    checkpointer = InMemorySaver()
    with patch("app.services.evaluation._retrieved_sources", return_value=[]):
        result = run_case(
            db_session, case, checkpointer, created_by=user.id,
            agent_model=ScriptedModel(responses=[_tool_call("generate_plan")]),
            classifier=lambda text: "feature",
            plan_generator=lambda *a: _plan(confidence="low", evidence=[]),
        )

    assert result.actual_behavior == EvaluationBehavior.insufficient_evidence
    assert result.passed is True


def test_run_dataset_runs_every_case_for_the_project(db_session):
    user, project = _make_project(db_session)
    _make_case(db_session, project, title="a")
    _make_case(db_session, project, title="b")
    checkpointer = InMemorySaver()

    with patch("app.services.evaluation._retrieved_sources", return_value=[]):
        results = run_dataset(
            db_session, project.id, checkpointer, created_by=user.id,
            agent_model=ScriptedModel(responses=[_tool_call("generate_plan")]),
            classifier=lambda text: "feature",
            plan_generator=lambda *a: _plan(),
        )

    assert len(results) == 2


# --- compute_report: pure metric math over directly-constructed rows, no agent involved ---


def _result_for(case, **overrides):
    base = dict(
        case_id=case.id,
        run_id=None,
        actual_behavior=case.expected_behavior,
        retrieved_sources=[],
        affected_files=[],
        evidence_chunk_ids=[],
        confidence=None,
        passed=True,
        notes="ok",
        latency_ms=100,
    )
    base.update(overrides)
    return EvaluationResult(**base)


def test_compute_report_retrieval_hit_rate_and_pass_rate(db_session):
    _, project = _make_project(db_session)
    hit_case = _make_case(db_session, project, expected_sources=["a.py"])
    miss_case = _make_case(db_session, project, expected_sources=["b.py"])

    db_session.add(_result_for(hit_case, retrieved_sources=["a.py", "c.py"], passed=True))
    db_session.add(_result_for(miss_case, retrieved_sources=["z.py"], passed=False, notes="miss"))
    db_session.commit()

    report = compute_report(db_session, project.id)

    assert report["total_cases"] == 2
    assert report["retrieval_hit_rate"] == 0.5
    assert report["overall_pass_rate"] == 0.5


def test_compute_report_uses_only_latest_result_per_case(db_session):
    # SQLite's CURRENT_TIMESTAMP (backing func.now()) only has second resolution, so two commits
    # in the same test would otherwise tie on created_at - set explicit, clearly-ordered timestamps
    # instead of relying on wall-clock gaps between them.
    import datetime

    _, project = _make_project(db_session)
    case = _make_case(db_session, project, expected_sources=["a.py"])

    older = _result_for(case, retrieved_sources=[], passed=False)
    older.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    newer = _result_for(case, retrieved_sources=["a.py"], passed=True)
    newer.created_at = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
    db_session.add_all([older, newer])
    db_session.commit()

    report = compute_report(db_session, project.id)

    assert report["total_results"] == 1
    assert report["overall_pass_rate"] == 1.0


def test_compute_report_clarification_accuracy(db_session):
    _, project = _make_project(db_session)
    good = _make_case(db_session, project, category=EvaluationCategory.ambiguous, expected_behavior=EvaluationBehavior.clarification)
    bad = _make_case(db_session, project, category=EvaluationCategory.ambiguous, expected_behavior=EvaluationBehavior.clarification)

    db_session.add(_result_for(good, actual_behavior=EvaluationBehavior.clarification, passed=True))
    db_session.add(_result_for(bad, actual_behavior=EvaluationBehavior.direct_answer, passed=False))
    db_session.commit()

    report = compute_report(db_session, project.id)
    assert report["clarification_accuracy"] == 0.5


def test_compute_report_affected_file_precision(db_session):
    _, project = _make_project(db_session)
    case = _make_case(db_session, project, expected_affected_files=["src/otp.py"])

    db_session.add(_result_for(case, affected_files=["src/otp.py", "src/unrelated.py"]))
    db_session.commit()

    report = compute_report(db_session, project.id)
    assert report["affected_file_precision"] == 0.5


def test_compute_report_citation_correctness_flags_dangling_chunk_ids(db_session):
    _, project = _make_project(db_session)
    document = Document(project_id=project.id, kind=ContentKind.code, filename="otp.py", status=DocumentStatus.ready)
    db_session.add(document)
    db_session.flush()
    chunk = ContentChunk(
        project_id=project.id,
        document_id=document.id,
        content_type=ContentKind.code,
        text="def verify(): ...",
        embedding=[0.0] * 384,
        source_metadata={"file_path": "src/otp.py"},
    )
    db_session.add(chunk)
    db_session.commit()

    case = _make_case(db_session, project)
    db_session.add(_result_for(case, evidence_chunk_ids=[str(chunk.id), str(uuid.uuid4())]))
    db_session.commit()

    report = compute_report(db_session, project.id)
    assert report["citation_correctness"] == 0.5


def test_compute_report_unsupported_claim_rate_flags_confident_but_ungrounded_plans(db_session):
    _, project = _make_project(db_session)
    case = _make_case(db_session, project)
    db_session.add(
        _result_for(case, actual_behavior=EvaluationBehavior.direct_answer, confidence="high", retrieved_sources=[])
    )
    db_session.commit()

    report = compute_report(db_session, project.id)
    assert report["unsupported_claim_rate"] == 1.0


def test_compute_report_with_no_cases_returns_nones(db_session):
    _, project = _make_project(db_session)
    report = compute_report(db_session, project.id)

    assert report["total_cases"] == 0
    assert report["overall_pass_rate"] is None
    assert report["retrieval_hit_rate"] is None
