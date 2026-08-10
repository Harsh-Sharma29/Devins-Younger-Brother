import re
from typing import Any, Dict

from src.core.memory import get_state_field

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


