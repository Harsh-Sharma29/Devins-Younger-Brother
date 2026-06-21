import re
from typing import Dict, Any, TYPE_CHECKING
from src.tools.file_ops import write_code_to_disk, write_workspace_to_disk
from src.core.llm_fallback import call_agent_llm, sanitize_code_for_buffer
from src.core.memory import format_history_context, record_assistant_turn

if TYPE_CHECKING:
	from src.core.graph import DevinBrotherState

CODER_SYSTEM_PROMPT = (
	"You are an expert Python developer. Return ONLY valid Python code.\n"
	"When the task requires multiple files, output them using this separator format:\n"
	"# --- FILE: filename.py ---\n"
	"<code for that file>\n"
	"# --- FILE: another_file.py ---\n"
	"<code for another file>\n\n"
	"If only one file is needed, wrap it in a single markdown code fence.\n"
	"The entry point file should be named main.py unless the user specifies otherwise.\n"
	"Code must run in an isolated Docker sandbox. Always wrap network and file I/O in try/except blocks.\n"
	"Never embed API keys or secrets. Never use os.remove, shutil.rmtree, eval, exec, or shell=True subprocess calls.\n"
	"For HTTP calls, use Python's built-in urllib.request — do NOT import 'requests' (it's not available)."
)

_FILE_SEPARATOR_RE = re.compile(
	r"^#\s*---\s*FILE:\s*(.+?)\s*---\s*$",
	re.MULTILINE,
)


def _parse_multi_file_output(raw: str) -> Dict[str, str]:
	"""Parse multi-file LLM output using '# --- FILE: name ---' separators.
	Falls back to single-file if no separators are found."""
	matches = list(_FILE_SEPARATOR_RE.finditer(raw))
	if not matches:
		return {}

	files: Dict[str, str] = {}
	for i, match in enumerate(matches):
		filename = match.group(1).strip()
		start = match.end()
		end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
		content = raw[start:end].strip()
		# Strip markdown code fences if present within each file block
		if content.startswith("```"):
			lines = content.split("\n")
			# Remove opening fence
			lines = lines[1:]
			# Remove closing fence
			if lines and lines[-1].strip() == "```":
				lines = lines[:-1]
			content = "\n".join(lines).strip()
		if filename and content:
			files[filename] = content
	return files


def _determine_entry_file(files: Dict[str, str]) -> str:
	"""Determine the main entry point file from workspace files."""
	priority = ["main.py", "app.py", "run.py", "index.py"]
	for name in priority:
		if name in files:
			return name
	# Fallback: first .py file alphabetically
	py_files = sorted(f for f in files if f.endswith(".py"))
	return py_files[0] if py_files else "main.py"


def _append_log(state: Any, line: str) -> list[str]:
	if isinstance(state, dict):
		logs = list(state.get("pipeline_logs") or [])
	else:
		logs = list(getattr(state, "pipeline_logs", []) or [])
	logs.append(line)
	return logs


def coder_agent(state: Any) -> Dict[str, Any]:
	"""Generate Python via Gemini with Hugging Face Hub failover and memory context."""
	if isinstance(state, dict):
		user_prompt = state.get("user_prompt") or "Write a basic python script."
		pipeline_logs = state.get("pipeline_logs") or []
		used_hf_failover = state.get("used_hf_failover") or False
		terminal_output = state.get("terminal_output") or ""
		llm_provider = state.get("llm_provider") or "gemini"
		validator_feedback = state.get("validator_feedback") or []
		history = state.get("conversation_history") or []
	else:
		user_prompt = getattr(state, "user_prompt", "") or "Write a basic python script."
		pipeline_logs = getattr(state, "pipeline_logs", []) or []
		used_hf_failover = getattr(state, "used_hf_failover", False) or False
		terminal_output = getattr(state, "terminal_output", "") or ""
		llm_provider = getattr(state, "llm_provider", "gemini") or "gemini"
		validator_feedback = getattr(state, "validator_feedback", []) or []
		history = getattr(state, "conversation_history", []) or []

	logs = _append_log(state, "[Coder] Invoking LLM (primary: Gemini)…")
	context = format_history_context(history)

	user_message = (
		f"Conversation context (last exchanges):\n{context}\n\n"
		f"Task:\n{user_prompt}"
	)
	if validator_feedback:
		feedback_block = "\n".join(f"- {item}" for item in validator_feedback)
		user_message += (
			f"\n\n[Validator — rewrite required before sandbox]:\n{feedback_block}\n"
			"Fix every issue above. Return the full corrected Python file only."
		)
		logs.append("[Coder] Incorporating Validator self-reflection feedback…")

	try:
		llm_result = call_agent_llm(CODER_SYSTEM_PROMPT, user_message)
		provider_label = "Hugging Face Hub" if llm_result.used_failover else "Gemini"
		logs.append(
			f"[Coder] Response received via {provider_label}"
			+ (" (failover active)" if llm_result.used_failover else "")
		)

		# Try multi-file parse first
		workspace_files = _parse_multi_file_output(llm_result.content)

		if workspace_files:
			# Multi-file output detected
			entry_file = _determine_entry_file(workspace_files)
			filenames = list(workspace_files.keys())
			logs.append(f"[Coder] Multi-file workspace: {', '.join(filenames)} (entry: {entry_file})")

			# Write all files to disk
			write_workspace_to_disk(workspace_files)

			# code_buffer mirrors the entry file for display/validation
			code = workspace_files.get(entry_file, "")
			history = record_assistant_turn(
				history,
				f"Generated {len(filenames)} files: {', '.join(filenames)}"
			)

			return {
				"code_buffer": code,
				"workspace_files": workspace_files,
				"active_file": entry_file,
				"detected_errors": [],
				"pipeline_logs": logs,
				"conversation_history": history,
				"llm_provider": llm_result.provider,
				"used_hf_failover": llm_result.used_failover or used_hf_failover,
				"terminal_output": terminal_output + f"\n[Coder] Generated {len(filenames)} files via {provider_label}.",
				"validation_passed": False,
				"validator_feedback": [],
			}

		# Single-file fallback
		code, err = sanitize_code_for_buffer(llm_result.content)
		if err or not code:
			logs.append(f"[Coder] Invalid payload rejected: {err}")
			return {
				"code_buffer": "",
				"detected_errors": [err or "Coder returned non-Python payload."],
				"pipeline_logs": logs,
				"llm_provider": llm_result.provider,
				"used_hf_failover": llm_result.used_failover or used_hf_failover,
				"terminal_output": terminal_output + "\n[Coder] Blocked invalid LLM output — not written to disk.",
				"validation_passed": False,
			}

		filename = "main.py"
		write_code_to_disk(filename, code)
		workspace = {filename: code}
		logs.append(f"[Coder] Wrote sanitized code → {filename}")
		history = record_assistant_turn(history, f"Generated {filename} ({len(code)} chars)")

		return {
			"code_buffer": code,
			"workspace_files": workspace,
			"active_file": filename,
			"detected_errors": [],
			"pipeline_logs": logs,
			"conversation_history": history,
			"llm_provider": llm_result.provider,
			"used_hf_failover": llm_result.used_failover or used_hf_failover,
			"terminal_output": terminal_output + f"\n[Coder] Generated via {provider_label}.",
			"validation_passed": False,
			"validator_feedback": [],
		}

	except Exception as exc:
		logs.append(f"[Coder] LLM failure: {exc}")
		return {
			"code_buffer": "",
			"detected_errors": [str(exc)],
			"pipeline_logs": logs,
			"llm_provider": llm_provider,
			"used_hf_failover": used_hf_failover,
			"terminal_output": terminal_output + f"\n[Coder] Error: {exc}",
			"validation_passed": False,
		}
