"""
Devin's Younger Brother — FastAPI Backend
Owns LangGraph execution, Postgres checkpointing, Docker sandbox, and telemetry.
The Streamlit frontend connects here via HTTP/SSE.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from src.core.checkpointer import (
    check_postgres_health,
    get_app,
    is_using_fallback,
    cleanup_resources,
)
from src.core.config import DEFAULT_RECURSION_LIMIT, build_run_config
from src.core.graph import get_initial_state
from src.core.telemetry import (
    default_telemetry,
    estimate_tokens,
    node_transition_line,
    tick_telemetry,
    telemetry_from_state,
)

import os

logger = logging.getLogger("dyb.api")
logging.basicConfig(level=logging.INFO)


# ─── LIFESPAN ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize LangGraph + Postgres pool on startup; cleanup on shutdown."""
    logger.info("Starting Devin's Younger Brother API server")
    try:
        get_app()  # Eagerly compile the graph + init checkpointer
        logger.info("LangGraph application compiled successfully")
    except Exception as exc:
        logger.error("Failed to compile LangGraph app on startup: %s", exc)
    yield
    logger.info("Shutting down API server — cleaning up resources")
    cleanup_resources()


# ─── APP ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Devin's Younger Brother API",
    version="1.0.0",
    description="Backend API for LangGraph pipeline execution with Postgres persistence.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8502",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REQUEST/RESPONSE MODELS ───────────────────────────────────────────────────
class ExecuteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The user prompt to execute")
    thread_id: str = Field(..., min_length=1, description="Session thread ID for checkpointing")
    recursion_limit: int = Field(default=DEFAULT_RECURSION_LIMIT, ge=10, le=100)


class HealthResponse(BaseModel):
    postgres: Dict[str, str]
    gemini_ok: bool
    hf_ok: bool
    using_fallback: bool
    telemetry: Dict[str, Any]


class SessionResponse(BaseModel):
    thread_id: str


class HistoryResponse(BaseModel):
    thread_id: str
    conversation_history: List[Dict[str, str]]


# ─── HELPERS ────────────────────────────────────────────────────────────────────
def _coerce_state_dict(state: Any) -> Dict[str, Any]:
    """Convert LangGraph state (Pydantic model or dict) to plain dict."""
    if state is None:
        return {}
    if hasattr(state, "model_dump"):
        return state.model_dump()
    if hasattr(state, "dict"):
        return state.dict()
    if isinstance(state, dict):
        return dict(state)
    return {}


def _merge_accumulated_state(
    accumulated: Dict[str, Any], update: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge incremental node updates into accumulated state."""
    merged = dict(accumulated)
    for key, value in update.items():
        if value is None:
            continue
        if key == "pipeline_logs" and isinstance(value, list):
            merged[key] = list(value)
        elif key == "workspace_files" and isinstance(value, dict):
            existing = dict(merged.get("workspace_files") or {})
            existing.update(value)
            merged[key] = existing
        else:
            merged[key] = value
    return merged


def _build_input_state(
    langgraph_app: Any, user_prompt: str, run_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the initial state, restoring conversation history from checkpoints."""
    input_state = get_initial_state(user_prompt)
    try:
        snapshot = langgraph_app.get_state(run_config)
        if snapshot is not None and getattr(snapshot, "values", None) is not None:
            prior = _coerce_state_dict(snapshot.values)
            history = prior.get("conversation_history") or []
            if history:
                input_state["conversation_history"] = list(history)
    except Exception:
        pass
    return input_state


# ─── ENDPOINTS ──────────────────────────────────────────────────────────────────
@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    """Return system health: Postgres status, API keys, telemetry."""
    pg = check_postgres_health()
    tel = default_telemetry()
    return HealthResponse(
        postgres=pg,
        gemini_ok=bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        hf_ok=bool(os.getenv("HUGGINGFACEHUB_API_TOKEN")),
        using_fallback=is_using_fallback(),
        telemetry={
            "cpu_pct": round(tel.get("cpu_pct", 0.0), 1),
            "ram_pct": round(tel.get("ram_pct", 0.0), 1),
            "total_tokens": 0,
            "latency_ms": 0,
        },
    )


@app.post("/api/v1/session/new", response_model=SessionResponse)
async def new_session():
    """Generate a new backend-authoritative thread ID."""
    return SessionResponse(thread_id=str(uuid.uuid4()))


@app.get("/api/v1/history/{thread_id}", response_model=HistoryResponse)
async def get_history(thread_id: str):
    """Retrieve conversation history for a given thread ID."""
    try:
        langgraph_app = get_app()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load LangGraph app: {exc}")

    run_config = build_run_config(thread_id)
    try:
        import anyio
        snapshot = await anyio.to_thread.run_sync(langgraph_app.get_state, run_config)
        if snapshot is not None and getattr(snapshot, "values", None) is not None:
            state_dict = _coerce_state_dict(snapshot.values)
            history = state_dict.get("conversation_history") or []
            return HistoryResponse(thread_id=thread_id, conversation_history=history)
    except Exception as exc:
        logger.exception("Failed to retrieve state snapshot for thread %s", thread_id)
        raise HTTPException(status_code=500, detail=f"Error fetching history: {exc}")

    return HistoryResponse(thread_id=thread_id, conversation_history=[])


@app.post("/api/v1/execute")
async def execute_pipeline(req: ExecuteRequest):
    """
    Execute the LangGraph pipeline and stream results via SSE.

    Events:
    - node_update: incremental state from each graph node
    - complete: final accumulated state
    - error: exception details
    """

    async def event_generator():
        import asyncio
        import anyio
        from concurrent.futures import ThreadPoolExecutor

        try:
            langgraph_app = get_app()
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc), "phase": "init"}),
            }
            return

        run_config = build_run_config(
            req.thread_id, recursion_limit=req.recursion_limit
        )
        input_state = _build_input_state(langgraph_app, req.prompt, run_config)

        accumulated: Dict[str, Any] = {}
        seen_log_count = 0
        step_idx = 0
        telemetry = default_telemetry()

        # Set up a queue and thread pool to run the synchronous stream iterator off the main event loop
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def run_graph_stream():
            try:
                for event in langgraph_app.stream(
                    input_state, config=run_config, stream_mode="updates"
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, ("event", event))
                loop.call_soon_threadsafe(queue.put_nowait, ("complete", None))
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))

        executor = ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, run_graph_stream)

        try:
            while True:
                msg_type, val = await queue.get()
                if msg_type == "complete":
                    break
                elif msg_type == "error":
                    raise val

                # val is {node_name: update}
                for node_name, update in val.items():
                    if not update:
                        continue

                    transition = node_transition_line(node_name, "Active")
                    patch = _coerce_state_dict(update)
                    accumulated = _merge_accumulated_state(accumulated, patch)

                    # Extract new pipeline_logs since last event
                    logs = accumulated.get("pipeline_logs") or []
                    new_logs = logs[seen_log_count:]
                    seen_log_count = len(logs)

                    # Terminal output delta
                    term_delta = ""
                    term = patch.get("terminal_output")
                    if isinstance(term, str) and term.strip():
                        term_delta = term.strip()

                    # Workspace + code
                    workspace = accumulated.get("workspace_files") or {}
                    active_file = accumulated.get("active_file") or "main.py"
                    code_buffer = str(
                        workspace.get(active_file, "")
                        or accumulated.get("code_buffer")
                        or ""
                    )

                    # Tick telemetry
                    telemetry = tick_telemetry(
                        telemetry,
                        log_line="\n".join(new_logs),
                        code=code_buffer,
                        step_index=step_idx,
                        final=bool(accumulated.get("is_verified")),
                    )
                    step_idx += 1

                    payload = {
                        "node_name": node_name,
                        "transition": transition,
                        "new_logs": new_logs,
                        "terminal_output_delta": term_delta,
                        "workspace_files": workspace,
                        "active_file": active_file,
                        "code_buffer": code_buffer,
                        "is_verified": bool(accumulated.get("is_verified")),
                        "intent": accumulated.get("intent", "generic"),
                        "detected_errors": accumulated.get("detected_errors") or [],
                        "telemetry": {
                            k: v
                            for k, v in telemetry.items()
                            if not k.startswith("_")
                        },
                        "step_index": step_idx,
                    }

                    yield {
                        "event": "node_update",
                        "data": json.dumps(payload, default=str),
                    }
        except Exception as exc:
            logger.exception("Pipeline execution error")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc), "phase": "execution"}),
            }
            return
        finally:
            executor.shutdown(wait=False)

        # Final state from checkpoint
        try:
            snapshot = await anyio.to_thread.run_sync(langgraph_app.get_state, run_config)
            if snapshot is not None and getattr(snapshot, "values", None) is not None:
                final_state = _coerce_state_dict(snapshot.values)
            else:
                final_state = accumulated
        except Exception:
            final_state = accumulated

        final_telemetry = telemetry_from_state(final_state)

        # Build final payload — strip non-serializable fields
        final_payload = {
            "workspace_files": final_state.get("workspace_files") or {},
            "active_file": final_state.get("active_file") or "main.py",
            "code_buffer": final_state.get("code_buffer") or "",
            "terminal_output": final_state.get("terminal_output") or "",
            "pipeline_logs": final_state.get("pipeline_logs") or [],
            "is_verified": bool(final_state.get("is_verified")),
            "intent": final_state.get("intent", "generic"),
            "detected_errors": final_state.get("detected_errors") or [],
            "conversation_history": final_state.get("conversation_history") or [],
            "telemetry": {
                k: v for k, v in final_telemetry.items() if not k.startswith("_")
            },
        }

        yield {
            "event": "complete",
            "data": json.dumps(final_payload, default=str),
        }

    return EventSourceResponse(event_generator())
