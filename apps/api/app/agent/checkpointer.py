"""Shared LangGraph Postgres checkpointer - powers interrupt()/resume for the agent graph."""
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings


def _to_plain_conninfo(database_url: str) -> str:
    """Strip SQLAlchemy's '+psycopg' dialect marker - psycopg wants a plain postgresql:// URL."""
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_checkpointer():
    from langgraph.checkpoint.postgres import PostgresSaver

    pool = ConnectionPool(
        conninfo=_to_plain_conninfo(settings.database_url),
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
        # Managed/serverless Postgres (e.g. Neon) can silently close idle connections server-side;
        # without a health check, checking one of those back out fails with "SSL connection has
        # been closed unexpectedly" on first use. check_connection pings before handing one out and
        # transparently reconnects if it's dead, instead of surfacing that as a request failure.
        check=ConnectionPool.check_connection,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver
