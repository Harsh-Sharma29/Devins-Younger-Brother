"""
Postgres-backed LangGraph checkpointer lifecycle management.
Falls back to in-memory checkpointer if Postgres is unreachable.
"""

from __future__ import annotations

import atexit
import logging
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from src.core.config import get_database_url
from src.core.graph import compile_workflow

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_checkpointer: Optional[Any] = None
_app: Optional[Any] = None
_using_fallback: bool = False


def check_postgres_health() -> dict:
    """Return Postgres connection health status for UI display."""
    global _pool, _using_fallback
    if _using_fallback:
        return {"status": "fallback", "label": "In-Memory Fallback"}
    if _pool is None:
        return {"status": "disconnected", "label": "Not initialized"}
    try:
        conn = _pool.getconn()
        try:
            cur = conn.execute("SELECT 1")
            cur.close()
        finally:
            _pool.putconn(conn)
        return {"status": "connected", "label": "Connected"}
    except Exception as exc:
        logger.warning("Postgres health check failed: %s", exc)
        return {"status": "error", "label": f"Error: {exc}"}


def initialize_checkpointer() -> Any:
    """Create the connection pool, run schema setup, and return PostgresSaver.
    Falls back to MemorySaver if Postgres is unreachable."""
    global _pool, _checkpointer, _using_fallback

    if _checkpointer is not None:
        return _checkpointer

    database_url = get_database_url()
    logger.info("Initializing PostgresSaver (url host redacted)")

    try:
        _pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=10,
            kwargs={"autocommit": True},
        )
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()
        _using_fallback = False
        logger.info("Postgres checkpointer schema ready")
        return _checkpointer
    except Exception as exc:
        logger.warning(
            "Postgres checkpointer initialization failed (%s). "
            "Falling back to in-memory checkpointer. Sessions will NOT persist across restarts.",
            exc,
        )
        # Clean up partial pool
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None

        _checkpointer = MemorySaver()
        _using_fallback = True
        return _checkpointer


def get_app() -> Any:
    """Return the compiled LangGraph application with persistence."""
    global _app

    if _app is None:
        checkpointer = initialize_checkpointer()
        _app = compile_workflow(checkpointer)

    return _app


def is_using_fallback() -> bool:
    """Check if we are using the in-memory checkpointer fallback."""
    return _using_fallback


def cleanup_resources() -> None:
    """Close connections on shutdown."""
    global _pool
    if _pool is not None:
        try:
            logger.info("Closing checkpointer database pool")
            _pool.close()
        except Exception as exc:
            logger.error("Error closing checkpointer database pool: %s", exc)
        finally:
            _pool = None


atexit.register(cleanup_resources)
