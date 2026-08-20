from typing import Dict, Any, TYPE_CHECKING

from src.tools.file_ops import write_code_to_disk, write_workspace_to_disk
from src.core.llm_fallback import call_agent_llm, sanitize_code_for_buffer
from src.core.memory import get_state_field

if TYPE_CHECKING:
    from src.core.graph import AutoForgeState

DEBUGGER_SYSTEM_INSTRUCTION = (
    "You are an expert Python debugger running inside an autonomous repair loop. "
    "Return ONLY a complete, valid Python program inside markdown code fences. "
    "CRITICAL: You are an autonomous debugger inside a loop. If the console logs show a "
    "NameError or syntax typo, you must completely rewrite the code block to replace the "
    "broken tokens with valid Python syntax. Do not wrap the fix inside another nested error layer. "
    "CRITICAL: The code runs inside a bare minimum Docker container without internet or "
    "external pip packages like 'requests'. If you see ModuleNotFoundError for 'requests', "
    "rewrite HTTP logic using Python's built-in urllib.request and json. DO NOT import external packages. "
    "Output executable Python only — no explanations, no partial patches."
)


def _append_log(state: Any, line: str) -> list[str]:
    if isinstance(state, dict):
        logs = list(state.get("pipeline_logs") or [])
    else:
        logs = list(getattr(state, "pipeline_logs", []) or [])
    logs.append(line)
    return logs


def debugger_agent(state: Any) -> Dict[str, Any]:
    """
    Repair failed sandbox runs. Clears detected_errors before re-terminal.
    Maintains workspace_files consistency for multi-file projects.
    Never persists raw API error JSON into code_buffer.
    """
    code_buffer = get_state_field(state, "code_buffer", "") or ""
    prior_buffer = code_buffer.strip()
    attempt = (get_state_field(state, "repair_attempts", 0) or 0) + 1
    user_prompt = get_state_field(state, "user_prompt", "") or ""
    planner_suggestion = get_state_field(state, "planner_suggestion", "") or ""
    detected_errors = get_state_field(state, "detected_errors", []) or []
    terminal_output = get_state_field(state, "terminal_output", "") or ""
    used_hf_failover = get_state_field(state, "used_hf_failover", False) or False
    workspace_files = dict(get_state_field(state, "workspace_files", {}) or {})
    active_file = get_state_field(state, "active_file", "main.py") or "main.py"

    logs = _append_log(
        state,
        f"[Debugger] Repair attempt {attempt} — invoking LLM (primary: Gemini)…",
    )

    errors = "\n".join(detected_errors)
    user_message = (
        f"Original Request: {user_prompt}\n\n"
        f"Planner Suggestion: {planner_suggestion}\n\n"
        f"Faulty Code:\n```python\n{code_buffer}\n```\n\n"
        f"Error Trace:\n{errors}\n\n"
        "Fix the entire script so it executes cleanly in an isolated Docker sandbox. "
        "Return ONLY the full corrected Python file."
    )

    try:
        llm_result = call_agent_llm(DEBUGGER_SYSTEM_INSTRUCTION, user_message)
        provider_label = "Hugging Face Hub" if llm_result.used_failover else "Gemini"
        logs.append(
            f"[Debugger] Response via {provider_label}"
            + (" (failover active)" if llm_result.used_failover else "")
        )

        fixed_code, err = sanitize_code_for_buffer(llm_result.content)
        if err or not fixed_code:
            logs.append(f"[Debugger] Invalid payload rejected: {err}")
            return {
                "code_buffer": prior_buffer,
                "detected_errors": [err or "Debugger returned non-Python payload."],
                "is_verified": False,
                "last_code_buffer": prior_buffer,
                "repair_attempts": attempt,
                "pipeline_logs": logs,
                "llm_provider": llm_result.provider,
                "used_hf_failover": llm_result.used_failover or used_hf_failover,
                "terminal_output": terminal_output
                + f"\n[Debugger] Rejected invalid LLM output; prior buffer retained.",
            }

        # Write fixed code to disk and update workspace
        write_code_to_disk(active_file, fixed_code)
        workspace_files[active_file] = fixed_code

        if fixed_code.strip() == prior_buffer and prior_buffer:
            logs.append("[Debugger] No code change detected — halting repair loop.")
            return {
                "code_buffer": fixed_code,
                "workspace_files": workspace_files,
                "detected_errors": [],
                "is_verified": False,
                "last_code_buffer": prior_buffer,
                "repair_attempts": attempt,
                "pipeline_logs": logs,
                "llm_provider": llm_result.provider,
                "used_hf_failover": llm_result.used_failover or used_hf_failover,
                "terminal_output": terminal_output
                + "\n[Debugger] No code change detected — halting repair loop.",
            }

        logs.append("[Debugger] Errors flushed; scheduling sandbox re-run.")
        return {
            "code_buffer": fixed_code,
            "workspace_files": workspace_files,
            "detected_errors": [],
            "is_verified": False,
            "last_code_buffer": prior_buffer,
            "repair_attempts": attempt,
            "pipeline_logs": logs,
            "llm_provider": llm_result.provider,
            "used_hf_failover": llm_result.used_failover or used_hf_failover,
            "terminal_output": terminal_output
            + f"\n[Debugger] Repair attempt {attempt} via {provider_label}: errors flushed, re-running sandbox…",
        }

    except Exception as exc:
        logs.append(f"[Debugger] LLM failure: {exc}")
        return {
            "code_buffer": prior_buffer,
            "detected_errors": [str(exc)],
            "is_verified": False,
            "last_code_buffer": prior_buffer,
            "repair_attempts": attempt,
            "pipeline_logs": logs,
            "terminal_output": terminal_output + f"\n[Debugger] Error: {exc}",
        }
