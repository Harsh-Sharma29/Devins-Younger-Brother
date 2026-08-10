"""
Self-reflection validator — static QA before Docker sandbox execution.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Tuple

from src.core.memory import get_state_field

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

_API_KEY_PATTERNS = [
    (r'(?i)(api[_-]?key|secret|token|password)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded credential assignment"),
    (r"\bsk-[a-zA-Z0-9]{20,}\b", "Possible OpenAI-style API key"),
    (r"\bAIza[0-9A-Za-z\-_]{20,}\b", "Possible Google API key"),
    (r"\bghp_[a-zA-Z0-9]{20,}\b", "Possible GitHub token"),
    (r"\bhf_[a-zA-Z0-9]{20,}\b", "Possible Hugging Face token"),
]


def _validate_network_calls_in_try(code: str) -> List[str]:
    """Check if network calls are wrapped in a try/except block using AST."""
    reasons = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError during validation: {e}"]

    network_modules = {"requests", "urllib", "http", "aiohttp", "httpx"}

    class NetworkCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_try = False
            self.violations = []

        def visit_Try(self, node):
            old_in_try = self.in_try
            
            # The try block body
            self.in_try = True
            for stmt in node.body:
                self.visit(stmt)
                
            # Exception handlers, else, and finally blocks shouldn't inherit the try protection
            self.in_try = old_in_try
            for handler in node.handlers:
                self.visit(handler)
            for stmt in node.orelse:
                self.visit(stmt)
            for stmt in node.finalbody:
                self.visit(stmt)

        # Explicit pass-through for nested control flows to guarantee state persistence
        def visit_With(self, node):
            self.generic_visit(node)

        def visit_For(self, node):
            self.generic_visit(node)

        def visit_If(self, node):
            self.generic_visit(node)

        def visit_Call(self, node):
            if not self.in_try:
                call_name = ""
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        call_name = f"{node.func.value.id}.{node.func.attr}"
                    elif isinstance(node.func.value, ast.Attribute):
                        if isinstance(node.func.value.value, ast.Name):
                            call_name = f"{node.func.value.value.id}.{node.func.value.attr}.{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    call_name = node.func.id

                for mod in network_modules:
                    if call_name.startswith(mod):
                        self.violations.append(f"Line {node.lineno}: '{call_name}'")
                        break

            self.generic_visit(node)

    visitor = NetworkCallVisitor()
    visitor.visit(tree)

    for violation in visitor.violations:
        reasons.append(f"✗ Missing error handling: {violation} is not wrapped in a try/except block.")

    return reasons


def validate_code(code: str) -> Tuple[bool, List[str]]:
    """Return (passed, list of rejection reasons)."""
    reasons: List[str] = []
    if not (code or "").strip():
        return False, ["Empty code buffer — nothing to validate."]

    for pattern, message in _DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.I | re.M):
            reasons.append(message)

    for pattern, message in _API_KEY_PATTERNS:
        if re.search(pattern, code, re.I | re.M):
            reasons.append(message)

    network_reasons = _validate_network_calls_in_try(code)
    reasons.extend(network_reasons)

    return (len(reasons) == 0, reasons)


def validator_node(state: Any) -> Dict[str, Any]:
    """QA gate before sandbox — logs rejection reasons to pipeline_logs."""
    code = get_state_field(state, "code_buffer", "") or ""
    pipeline_logs: List[str] = list(get_state_field(state, "pipeline_logs", []) or [])
    attempts = int(get_state_field(state, "validator_attempts", 0) or 0)

    passed, reasons = validate_code(code)

    if passed:
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

    feedback = reasons
    pipeline_logs.append("[Validator] REJECTED — code blocked before sandbox:")
    for reason in feedback:
        pipeline_logs.append(f"[Validator]   ✗ {reason}")
    pipeline_logs.append(
        "[Validator] Routing back to Coder for rewrite (self-reflection loop)."
    )

    return {
        "validation_passed": False,
        "validator_feedback": feedback,
        "detected_errors": feedback,
        "pipeline_logs": pipeline_logs,
        "validator_attempts": attempts + 1,
        "coder_messages": [],
        "coder_tool_rounds": 0,
    }
