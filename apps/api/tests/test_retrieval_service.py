import uuid
from unittest.mock import patch

from app.models.approval import Approval
from app.models.change_request import ChangeRequest
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ApprovalDecision, ContentKind, DocumentStatus
from app.models.generated_plan import GeneratedPlan
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services.retrieval import find_similar_stories, get_chunk_context

# search_chunks() uses pgvector's cosine_distance operator, which only real Postgres understands -
# SQLite has no equivalent, so that path is covered by manual verification against the real DB
# (README "Verifying the agent workflow"), not here, matching the Phase 2 precedent for /search.


def _make_project_with_chunks(db_session):
    user = User(email="grounding@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    project = Project(name="P", owner_id=user.id)
    db_session.add(project)
    db_session.flush()
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id))

    document = Document(project_id=project.id, kind=ContentKind.code, filename="otp.py", status=DocumentStatus.ready)
    db_session.add(document)
    db_session.flush()

    chunk_a = ContentChunk(
        project_id=project.id,
        document_id=document.id,
        content_type=ContentKind.code,
        text="def verify_otp(): ...",
        embedding=[1.0, 0.0] + [0.0] * 382,
        source_metadata={"file_path": "src/otp.py", "symbol_name": "verify_otp"},
    )
    chunk_b = ContentChunk(
        project_id=project.id,
        document_id=document.id,
        content_type=ContentKind.code,
        text="class LoanApplication: ...",
        embedding=[0.0, 1.0] + [0.0] * 382,
        source_metadata={"file_path": "src/loan.py", "symbol_name": "LoanApplication"},
    )
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()
    return user, project, document, chunk_a, chunk_b


def test_get_chunk_context_returns_neighbors_in_same_document(db_session):
    _, _, _, chunk_a, chunk_b = _make_project_with_chunks(db_session)

    context = get_chunk_context(db_session, chunk_a.id, window=1)

    ids = {c.id for c in context}
    assert chunk_a.id in ids
    assert chunk_b.id in ids  # same document, adjacent by creation order


def test_get_chunk_context_unknown_chunk_returns_empty(db_session):
    assert get_chunk_context(db_session, uuid.uuid4()) == []


def _fake_embed(text: str) -> list[float]:
    # Deterministic stand-in for the real embedding model - keeps this test fast and offline.
    return [1.0, 0.0] if "otp" in text.lower() else [0.0, 1.0]


def test_find_similar_stories_returns_empty_when_no_approved_plans(db_session):
    _, project, _, _, _ = _make_project_with_chunks(db_session)
    assert find_similar_stories(db_session, project.id, "anything") == []


@patch("app.services.retrieval.embed_text", side_effect=_fake_embed)
def test_find_similar_stories_ranks_approved_plans_by_similarity(mock_embed, db_session):
    user, project, _, _, _ = _make_project_with_chunks(db_session)

    change_request = ChangeRequest(project_id=project.id, created_by=user.id, request_text="add otp")
    db_session.add(change_request)
    db_session.flush()

    plan = GeneratedPlan(
        change_request_id=change_request.id,
        run_id=uuid.uuid4(),
        version=1,
        content={"summary": "Add OTP verification before loan submission"},
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(Approval(plan_id=plan.id, reviewer_id=user.id, decision=ApprovalDecision.approved))
    db_session.commit()

    results = find_similar_stories(db_session, project.id, "otp check")

    assert len(results) == 1
    assert "OTP" in results[0][0]
    assert results[0][1] == 1.0  # identical fake-embed vector -> cosine similarity 1.0
