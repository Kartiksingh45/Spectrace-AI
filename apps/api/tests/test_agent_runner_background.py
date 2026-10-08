import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus, ChangeRequestStatus, RequestType
from app.models.agent_run import AgentRun
from app.models.project import Project
from app.models.user import User, UserRole
from app.services.agent_runner import run_in_background


@pytest.fixture()
def engine_and_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield SessionLocal
    engine.dispose()


def _seed_run(SessionLocal):
    """Mirrors what a real request handler does: create the rows, commit, then close - exactly
    what FastAPI's Depends(get_db) does to the request's session before a BackgroundTask runs."""
    db = SessionLocal()
    user = User(email="owner@example.com", password_hash="x", role=UserRole.administrator)
    db.add(user)
    db.commit()
    project = Project(name="proj", owner_id=user.id)
    db.add(project)
    db.commit()
    change_request = ChangeRequest(
        project_id=project.id,
        created_by=user.id,
        request_text="do the thing",
        request_type=RequestType.feature,
        status=ChangeRequestStatus.analysing,
    )
    db.add(change_request)
    db.commit()
    run = AgentRun(change_request_id=change_request.id, thread_id=str(uuid.uuid4()), status=AgentRunStatus.running)
    db.add(run)
    db.commit()
    run_id, change_request_id = run.id, change_request.id
    db.close()  # <-- the exact moment a request's Depends(get_db) session gets torn down
    return run_id, change_request_id


def test_run_in_background_persists_mutations_after_session_close(engine_and_factory):
    """Regression test for a real production bug: a run that genuinely finished and generated a
    plan stayed stuck showing "running" forever, because the background task mutated `run.status`
    on an object loaded under the request's own session - already closed (and its objects
    expunged) by the time the background task actually ran, so the mutation silently never made it
    into the commit. run_in_background must open its own session and re-fetch by id instead of
    being handed already-detached ORM objects.
    """
    SessionLocal = engine_and_factory
    run_id, change_request_id = _seed_run(SessionLocal)

    def fake_fn(db, run, change_request):
        run.status = AgentRunStatus.awaiting_approval
        change_request.status = ChangeRequestStatus.awaiting_approval
        db.commit()

    run_in_background(SessionLocal, fake_fn, run_id, change_request_id)

    verify = SessionLocal()
    try:
        persisted_run = verify.get(AgentRun, run_id)
        persisted_change_request = verify.get(ChangeRequest, change_request_id)
        assert persisted_run.status == AgentRunStatus.awaiting_approval
        assert persisted_change_request.status == ChangeRequestStatus.awaiting_approval
    finally:
        verify.close()


def test_run_in_background_closes_its_own_session(engine_and_factory):
    SessionLocal = engine_and_factory
    run_id, change_request_id = _seed_run(SessionLocal)
    captured = {}

    def fake_fn(db, run, change_request):
        captured["db"] = db

    run_in_background(SessionLocal, fake_fn, run_id, change_request_id)

    # SQLAlchemy sessions stay reusable after close(), so assert closed via its own public flag
    # rather than expecting a subsequent operation to raise.
    assert captured["db"].in_transaction() is False
