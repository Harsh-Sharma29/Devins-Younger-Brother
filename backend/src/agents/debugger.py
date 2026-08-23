import json
from typing import Any, Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.core.llm_factory import get_llm
from src.core.memory import get_state_field
from src.core.types import DebuggerAction, PipelineStatus

def debugger_agent(state: Any) -> Dict[str, Any]:
    terminal_output = get_state_field(state, "terminal_output", "") or ""
    detected_errors = get_state_field(state, "detected_errors", []) or []
    workspace_files = get_state_field(state, "workspace_files", {})
    repair_attempts = int(get_state_field(state, "repair_attempts", 0) or 0)
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    active_file = get_state_field(state, "active_file", "main.py") or "main.py"

    pipeline_logs.append(f"[Debugger] Repair attempt {repair_attempts + 1}...")

    if not workspace_files:
        code_buffer = get_state_field(state, "code_buffer", "") or ""
        workspace_files = {active_file: code_buffer}

    files_context = ""
    for k, v in workspace_files.items():
        files_context += f"\n--- FILE: {k} ---\n{v}\n"

    system_prompt = (
        "You are an expert debugging assistant.\n"
        "Analyze the provided code and the execution error.\n"
        "Return a strictly structured JSON response detailing your action.\n"
        "If the error is completely unfixable or you do not need to change anything, set action to 'no_change'.\n"
        "Otherwise, set action to 'rewrite_file', specify the 'path', and provide the entire corrected 'content'."
    )
    
    user_prompt = f"Code files:\n{files_context}\n\nExecution Error:\n{terminal_output}\n\nErrors list: {detected_errors}\n"
    
    llm = get_llm(temperature=0)
    
    action_obj = None
    if hasattr(llm, "with_structured_output"):
        try:
            structured_llm = llm.with_structured_output(DebuggerAction)
            resp = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
            action_obj = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
        except Exception as e:
            pipeline_logs.append(f"[Debugger] Structured output failed: {e}")
            action_obj = {"action": "no_change", "reason": f"Structured output error: {e}"}
    else:
        # Fallback manual json extraction skipped for brevity; just assuming structured output works for gemini/groq
        action_obj = {"action": "no_change", "reason": "Structured output not supported on LLM"}

    action_type = action_obj.get("action", "no_change")
    reason = action_obj.get("reason", "")
    
    if action_type == "no_change" or action_type == "abort":
        pipeline_logs.append(f"[Debugger] {action_type.upper()}: {reason}")
        # Signal graph to stop by setting repair_attempts artificially high
        return {
            "pipeline_logs": pipeline_logs,
            "repair_attempts": 999,
            "pipeline_status": PipelineStatus.REPAIR_EXHAUSTED.value
        }

    path = action_obj.get("path")
    new_content = action_obj.get("content")

    if path and new_content:
        # If the file hasn't changed at all, abort to prevent infinite loops
        if workspace_files.get(path, "") == new_content.strip():
            pipeline_logs.append("[Debugger] No actual code changes detected in generated content. Aborting repair loop.")
            return {
                "pipeline_logs": pipeline_logs,
                "repair_attempts": 999,
                "pipeline_status": PipelineStatus.REPAIR_EXHAUSTED.value
            }
            
        workspace_files[path] = new_content.strip()
        pipeline_logs.append(f"[Debugger] Applied '{action_type}' to '{path}'")
        return {
            "workspace_files": workspace_files,
            "active_file": path,
            "code_buffer": new_content.strip(),
            "pipeline_logs": pipeline_logs,
            "repair_attempts": repair_attempts + 1
        }
        
    pipeline_logs.append("[Debugger] Invalid schema payload returned. No changes applied.")
    return {
        "pipeline_logs": pipeline_logs,
        "repair_attempts": repair_attempts + 1
    }
