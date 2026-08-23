from __future__ import annotations
import ast
import re
from typing import Any, Dict, List, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from src.core.llm_factory import get_llm
from src.core.memory import get_state_field
from src.core.types import ValidatorFeedback, ErrorTaxonomy

MAX_VALIDATOR_ATTEMPTS = 3

_DANGEROUS_PATTERNS = [
    (r"\bos\.remove\b", "Dangerous operation: os.remove"),
    (r"\bos\.unlink\b", "Dangerous operation: os.unlink"),
    (r"\bshutil\.rmtree\b", "Dangerous operation: shutil.rmtree"),
    (r"\bsubprocess\.(call|run|Popen)\b.*\bshell\s*=\s*True", "Dangerous: subprocess with shell=True"),
    (r"\brm\s+-rf\b", "Dangerous operation: rm -rf"),
    (r"\beval\s*\(", "Dangerous operation: eval()"),
    (r"\bexec\s*\(", "Dangerous operation: exec()"),
    (r"\b__import__\s*\(", "Dangerous operation: dynamic __import__"),
]

def validate_workspace(workspace_files: Dict[str, str], artifact_plan: Dict[str, Any], user_prompt: str) -> Tuple[bool, List[ValidatorFeedback]]:
    feedback = []
    if not workspace_files:
        feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.ARTIFACT_CONTRACT_ERROR, expected_path=None, message="Empty code buffer.", required_action="GENERATE_CODE"))
        return False, feedback

    runtime = artifact_plan.get("runtime", "Python")
    expected_files = artifact_plan.get("artifacts", [])
    entry_file = artifact_plan.get("entry_file", "")

    # 1. Artifact Verification
    if entry_file and entry_file not in workspace_files:
        feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.ARTIFACT_CONTRACT_ERROR, expected_path=entry_file, message=f"Missing entry file: {entry_file}", required_action="CREATE_OR_RENAME_ARTIFACT"))
    
    for f in expected_files:
        if f not in workspace_files:
            feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.ARTIFACT_CONTRACT_ERROR, expected_path=f, message=f"Missing expected artifact: {f}", required_action="CREATE_OR_RENAME_ARTIFACT"))

    if "__UNNAMED_FILE__" in workspace_files:
        feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.ARTIFACT_CONTRACT_ERROR, expected_path=None, message="Coder outputted unnamed code block instead of using markdown file dividers.", required_action="USE_FILE_DIVIDERS"))

    # 2. Path Security & Python AST Verification
    for filename, code in workspace_files.items():
        if "../" in filename or filename.startswith("/"):
            feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.VALIDATION_ERROR, expected_path=filename, message=f"Path traversal detected in {filename}", required_action="RENAME_ARTIFACT"))
        
        for pattern, message in _DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.I | re.M):
                feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.VALIDATION_ERROR, expected_path=filename, message=message, required_action="REMOVE_DANGEROUS_CODE"))
        
        if filename.endswith(".py") and runtime == "Python":
            try:
                # Ensure it can decode strictly without bad unicode
                code.encode('utf-8').decode('utf-8', 'strict')
                ast.parse(code)
            except SyntaxError as e:
                feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.SYNTAX_ERROR, expected_path=filename, message=f"SyntaxError: {e}", required_action="FIX_SYNTAX"))
            except UnicodeError as e:
                feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.SYNTAX_ERROR, expected_path=filename, message=f"Unicode Encoding Error: {e}", required_action="REMOVE_INVALID_UNICODE"))

    # 3. LLM Requirement Verification (Only if no structural errors)
    if not feedback:
        try:
            llm = get_llm(temperature=0.0)
            sys_msg = "You are a strict QA validator. Given the user's original request and the generated files, determine if the code satisfies the user requirements. If it perfectly satisfies all requirements, reply EXACTLY with 'PASS'. Otherwise, reply with 'FAIL: ' followed by a concise bulleted list of missing requirements."
            content = f"User Request:\n{user_prompt}\n\nGenerated Files:\n"
            for k, v in workspace_files.items():
                content += f"\n--- FILE: {k} ---\n{v}\n"
            
            resp = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=content)])
            result = resp.content.strip()
            if not result.startswith("PASS"):
                feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.VALIDATION_ERROR, expected_path=None, message=f"Requirement Validation Failed: {result}", required_action="FIX_REQUIREMENTS"))
        except Exception as e:
            feedback.append(ValidatorFeedback(error_type=ErrorTaxonomy.VALIDATION_ERROR, expected_path=None, message=f"LLM Requirement Validation Error: {e}", required_action="RETRY_VALIDATION"))

    return (len(feedback) == 0, feedback)

def validator_node(state: Any) -> Dict[str, Any]:
    workspace_files = get_state_field(state, "workspace_files", {}) or {}
    if not workspace_files:
        code = get_state_field(state, "code_buffer", "") or ""
        if code: workspace_files = {get_state_field(state, "active_file", "main.py"): code}

    artifact_plan = get_state_field(state, "artifact_plan", {}) or {}
    user_prompt = get_state_field(state, "user_prompt", "") or ""
    pipeline_logs: List[str] = list(get_state_field(state, "pipeline_logs", []) or [])
    attempts = int(get_state_field(state, "validator_attempts", 0) or 0)

    pipeline_logs.append("[Validator] Verifying artifacts and user requirements...")
    passed, feedback_objs = validate_workspace(workspace_files, artifact_plan, user_prompt)

    if passed:
        pipeline_logs.append(f"[Validator] Requirements verified.")
        pipeline_logs.append("[Validator] PASSED — code cleared for Docker sandbox.")
        return {
            "validation_passed": True,
            "validator_feedback": [],
            "detected_errors": [],
            "pipeline_logs": pipeline_logs,
            "validator_attempts": attempts,
            "coder_messages": [],
            "coder_tool_rounds": 0,
        }

    feedback_dicts = [fb.model_dump() for fb in feedback_objs]
    feedback_strings = [f"{fb.error_type.value} ({fb.expected_path}): {fb.message} -> Action: {fb.required_action}" for fb in feedback_objs]

    pipeline_logs.append("[Validator] REJECTED — code blocked before sandbox:")
    for reason_str in feedback_strings:
        pipeline_logs.append(f"[Validator]   ✗ {reason_str}")
    
    pipeline_logs.append("[Validator] Routing back to Coder for rewrite (self-reflection loop).")

    return {
        "validation_passed": False,
        "validator_feedback": feedback_strings,
        "detected_errors": feedback_strings,
        "pipeline_logs": pipeline_logs,
        "validator_attempts": attempts + 1,
        "coder_messages": [],
        "coder_tool_rounds": 0,
    }
