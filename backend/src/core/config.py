"""
Central configuration for Devin's Younger Brother.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Local / compose default — override via DATABASE_URL in production.
DEFAULT_DATABASE_URL = (
	"postgresql://devin:devin@localhost:5432/devin_brother?sslmode=disable"
)

DEFAULT_RECURSION_LIMIT = 50


def get_database_url() -> str:
	"""Return the Postgres connection string for LangGraph checkpointing."""
	override = os.getenv("DATABASE_URL", "").strip()
	return override or DEFAULT_DATABASE_URL


def build_run_config(
	thread_id: str,
	*,
	recursion_limit: int = DEFAULT_RECURSION_LIMIT,
	checkpoint_id: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	Build the LangGraph invoke/stream config with an isolated session thread.
	"""
	if not thread_id or not str(thread_id).strip():
		raise ValueError("thread_id is required for checkpointed graph invocations.")

	configurable: Dict[str, Any] = {"thread_id": str(thread_id).strip()}
	if checkpoint_id:
		configurable["checkpoint_id"] = checkpoint_id

	return {
		"configurable": configurable,
		"recursion_limit": int(recursion_limit),
	}
