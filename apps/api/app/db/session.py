import logging
import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# A remote/serverless Postgres (e.g. Neon) can drop or fail a connection attempt for a moment
# under transient network trouble; retrying the first ping a few times turns a one-off blip into a
# short delay instead of failing the whole request outright. Widened from 3x/0.5s after observing
# blips that outlasted that window in practice.
_CONNECT_RETRY_ATTEMPTS = 5
_CONNECT_RETRY_DELAY_SECONDS = 1.0


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        for attempt in range(1, _CONNECT_RETRY_ATTEMPTS + 1):
            try:
                db.execute(text("SELECT 1"))
                break
            except OperationalError:
                if attempt == _CONNECT_RETRY_ATTEMPTS:
                    raise
                logger.warning("DB connection attempt %d/%d failed, retrying", attempt, _CONNECT_RETRY_ATTEMPTS)
                db.rollback()
                time.sleep(_CONNECT_RETRY_DELAY_SECONDS)
        yield db
    finally:
        db.close()
