from typing import Dict, Any, TYPE_CHECKING
from src.tools.file_ops import execute_python_code
from src.core.memory import get_state_field

if TYPE_CHECKING:
    from src.core.graph import DevinBrotherState

def terminal_agent(state: 'DevinBrotherState') -> Dict[str, Any]:
    """
    Executes the generated code via the Docker sandbox.
    Supports multi-file workspaces with configurable entry points.
    """
    workspace_files = get_state_field(state, "workspace_files", {}) or {}
    active_file = get_state_field(state, "active_file", "main.py") or "main.py"

    # Determine entry file — prefer active_file, fallback through common names
    if workspace_files:
        if active_file in workspace_files:
            entry_file = active_file
        elif "main.py" in workspace_files:
            entry_file = "main.py"
        else:
            # Use first .py file
            py_files = sorted(f for f in workspace_files if f.endswith(".py"))
            entry_file = py_files[0] if py_files else active_file
    else:
        # Legacy single-file mode
        entry_file = "main.py"

    # Run the script
    result = execute_python_code(
        entry_file,
        entry_file=entry_file,
        workspace_files=workspace_files if workspace_files else None,
    )

    if result["returncode"] == 0:
        return {
            "terminal_output": result["stdout"],
            "detected_errors": [],
            "is_verified": True
        }
    else:
        # Include both stderr and stdout in case the error is logged to stdout
        error_msg = result["stderr"] if result["stderr"] else result["stdout"]

        return {
            "terminal_output": result["stdout"],
            "detected_errors": [error_msg],
            "is_verified": False
        }
