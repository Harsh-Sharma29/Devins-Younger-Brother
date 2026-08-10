"""
Planner agent — mission brief with sliding-window conversation memory.
"""

from __future__ import annotations

from typing import Any, Dict

from src.core.memory import format_history_context, get_state_field, record_assistant_turn


def _derive_plan(user_prompt: str) -> str:
    """Build a plan string directly from the live user prompt."""
    text = (user_prompt or "").strip()
    if not text:
        return "Awaiting a concrete user objective."
    headline = text.splitlines()[0].strip()
    if len(headline) > 160:
        headline = headline[:157] + "..."
    return f"Fulfill user request: {headline}"


def _suggest_file_structure(user_prompt: str) -> str:
    """Suggest a multi-file structure when the task appears complex enough."""
    text = (user_prompt or "").strip().lower()
    multi_file_signals = [
        "multiple files", "project", "package", "module",
        "utils", "helper", "config", "separate", "api and",
        "frontend and backend", "tests", "test suite",
    ]
    if any(signal in text for signal in multi_file_signals):
        return (
            " Consider structuring as a multi-file project: "
            "main.py (entry point), utils.py (helpers), and requirements.txt if external deps are needed."
        )
    return " Default strictly to a single-file workspace (main.py) for this script task. Suppress multi-file suggestions (utils.py, requirements.txt) unless explicitly asked."


def planner_agent(state: Any) -> Dict[str, Any]:
    user_prompt = get_state_field(state, "user_prompt", "") or ""
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    history = get_state_field(state, "conversation_history", []) or []

    context = format_history_context(history)
    suggestion = _derive_plan(user_prompt)
    file_hint = _suggest_file_structure(user_prompt)

    pipeline_logs.append(f"[Planner] Mission brief accepted → {suggestion}")
    if file_hint:
        pipeline_logs.append(f"[Planner] Multi-file hint:{file_hint}")
    pipeline_logs.append(f"[Planner] Memory window: {min(len(history), 10)} message(s) loaded")

    brief = (
        f"{user_prompt}\n[Planner]: {suggestion}{file_hint}\n"
        f"[Context — last exchanges]:\n{context}"
    )
    history = record_assistant_turn(history, f"Plan: {suggestion}")

    return {
        "planner_suggestion": suggestion + file_hint,
        "user_prompt": brief,
        "pipeline_logs": pipeline_logs,
        "conversation_history": history,
    }
