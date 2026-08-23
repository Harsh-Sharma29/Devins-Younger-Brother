from typing import Any, Dict
from src.core.memory import get_state_field, get_thread_id
from src.tools.file_ops import execute_python_code
from src.core.types import ErrorTaxonomy

def terminal_agent(state: Any, config: Any = None) -> Dict[str, Any]:
    active_file = get_state_field(state, "active_file", "main.py") or "main.py"
    workspace_files = get_state_field(state, "workspace_files", {})
    if not workspace_files:
        code_buffer = get_state_field(state, "code_buffer", "") or ""
        workspace_files = {active_file: code_buffer}
        
    artifact_plan = get_state_field(state, "artifact_plan", {})
    entry_file = artifact_plan.get("entry_file", active_file)
    runtime = artifact_plan.get("runtime", "Python")

    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    pipeline_logs.append(f"[Terminal] Sending '{entry_file}' to Sandbox...")

    thread_id = get_thread_id(config) if config else None

    result = execute_python_code(
        active_file,
        entry_file=entry_file,
        workspace_files=workspace_files,
        thread_id=thread_id,
        runtime=runtime
    )

    status = result.get("status")
    err_type = result.get("error_type")
    safety = result.get("safety_status")
    
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    full_output = f"{stdout}\n{stderr}".strip()

    is_verified = (status == "passed")
    detected_errors = []
    
    pipeline_logs.append(f"[Terminal] Execution {status.upper()}. ErrorType: {err_type}, Safety: {safety.upper()}")

    if not is_verified:
        detected_errors.append(stderr or stdout or "Unknown failure")
        pipeline_logs.append(f"[Terminal] Output\n{full_output}")

    return {
        "terminal_output": full_output,
        "is_verified": is_verified,
        "detected_errors": detected_errors,
        "pipeline_logs": pipeline_logs,
        "execution_status": status,
        "error_type": err_type,
        "safety_status": safety
    }
