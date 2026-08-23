from __future__ import annotations
import json
from typing import Any, Dict, List, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from src.core.llm_factory import get_llm
from src.core.memory import format_history_context, get_state_field, record_assistant_turn
from src.core.types import ArtifactContract, ErrorTaxonomy, PipelineStatus

def planner_agent(state: Any) -> Dict[str, Any]:
    user_prompt = get_state_field(state, "user_prompt", "") or ""
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    history = get_state_field(state, "conversation_history", []) or []

    context = format_history_context(history)
    
    pipeline_logs.append("[Planner] Analyzing request for artifact requirements...")
    system_prompt = (
        "You are an expert technical planner. Analyze the user request and output a precise artifact plan. "
        "Identify the task_type, artifacts (list of all file names needed), entry_file, "
        "runtime (must be exactly 'Browser', 'Python', or 'Unknown'), and requirements."
    )
    
    artifact_plan_dict = None
    llm = get_llm(temperature=0)
    
    for attempt in range(2):
        try:
            if hasattr(llm, "with_structured_output"):
                structured_llm = llm.with_structured_output(ArtifactContract)
                plan_obj = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
                artifact_plan_dict = plan_obj.model_dump() if hasattr(plan_obj, "model_dump") else plan_obj.dict()
                break
            else:
                resp = llm.invoke([SystemMessage(content=system_prompt + " Return ONLY valid JSON."), HumanMessage(content=user_prompt)])
                content = resp.content
                if "```json" in content: content = content.split("```json")[1].split("```")[0]
                elif "```" in content: content = content.split("```")[1].split("```")[0]
                artifact_plan_dict = json.loads(content)
                # Quick validation
                ArtifactContract(**artifact_plan_dict)
                break
        except Exception as e:
            pipeline_logs.append(f"[Planner] Structured output failed on attempt {attempt+1}: {e}")
            if attempt == 1:
                return {
                    "pipeline_status": PipelineStatus.FAILED.value,
                    "error_type": ErrorTaxonomy.STRUCTURED_OUTPUT_ERROR.value,
                    "pipeline_logs": pipeline_logs,
                }
            system_prompt += f"\nPREVIOUS ERROR: {e}. Fix the schema."

    suggestion = f"Project: {artifact_plan_dict.get('task_type')} | Entry: {artifact_plan_dict.get('entry_file')} | Runtime: {artifact_plan_dict.get('runtime')}"
    pipeline_logs.append(f"[Planner] Mission brief accepted → {suggestion}")
    
    brief = (
        f"{user_prompt}\n[Planner]: {suggestion}\n"
        f"[Artifacts]: {', '.join(artifact_plan_dict.get('artifacts', []))}\n"
        f"[Context]:\n{context}"
    )
    
    history = record_assistant_turn(history, f"Plan: {suggestion}")

    return {
        "planner_suggestion": suggestion,
        "artifact_plan": artifact_plan_dict,
        "user_prompt": brief,
        "pipeline_logs": pipeline_logs,
        "conversation_history": history,
    }
