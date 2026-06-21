import os
import tempfile
import shutil
import docker
import time
from typing import Dict, Optional


def sandbox_workspace_dir() -> str:
    """Workspace for generated scripts; override via DYB_SANDBOX_DIR for containers."""
    override = os.getenv("DYB_SANDBOX_DIR", "").strip()
    if override:
        workspace_dir = os.path.abspath(override)
    else:
        workspace_dir = os.path.join(tempfile.gettempdir(), "devin_brother_sandbox")
    os.makedirs(workspace_dir, exist_ok=True)
    return workspace_dir


def clear_sandbox_workspace() -> None:
    """Remove all files in the sandbox workspace directory before a fresh run."""
    workspace_dir = sandbox_workspace_dir()
    for item in os.listdir(workspace_dir):
        item_path = os.path.join(workspace_dir, item)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except OSError:
            pass


def write_code_to_disk(filename: str, code: str) -> str:
    """
    Writes the provided code to a specified filename inside the sandbox directory.
    Returns the absolute path to the saved file.
    """
    workspace_dir = sandbox_workspace_dir()
    file_path = os.path.join(workspace_dir, filename)

    # Create subdirectories if filename has path separators
    parent = os.path.dirname(file_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

    return file_path


def write_workspace_to_disk(files: Dict[str, str]) -> str:
    """
    Write multiple files to the sandbox workspace directory.
    Returns the workspace directory path.
    """
    workspace_dir = sandbox_workspace_dir()
    for filename, content in files.items():
        write_code_to_disk(filename, content)
    return workspace_dir


def execute_python_code(
    filename: str,
    *,
    entry_file: Optional[str] = None,
    workspace_files: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Executes a python file inside an ephemeral Docker container for sandbox isolation.
    Supports multi-file workspaces: if workspace_files is provided, all files are written
    before execution. If a requirements.txt exists, dependencies are installed first.
    Returns a dict with stdout, stderr, and returncode.
    """
    # Clear workspace directory first to avoid stale artifacts
    clear_sandbox_workspace()

    workspace_dir = sandbox_workspace_dir()

    # Write all workspace files if provided
    if workspace_files:
        write_workspace_to_disk(workspace_files)

    # Determine the entry point file
    run_file = entry_file or filename
    file_path = os.path.join(workspace_dir, run_file)

    if not os.path.exists(file_path):
        return {"stdout": "", "stderr": f"File not found: {file_path}", "returncode": 1}

    try:
        # Initialize Docker client
        client = docker.from_env()

        # Build the command — install requirements.txt first if it exists
        requirements_path = os.path.join(workspace_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            command = (
                f"pip install --quiet -r /sandbox/requirements.txt 2>/dev/null; "
                f"python /sandbox/{run_file}"
            )
            exec_command = ["sh", "-c", command]
        else:
            exec_command = ["python", f"/sandbox/{run_file}"]

        # Spin up ephemeral container, mount workspace as read-only volume
        container = client.containers.run(
            image="python:3.11-slim",
            command=exec_command,
            volumes={workspace_dir: {'bind': '/sandbox', 'mode': 'ro'}},
            detach=True
        )

        # Wait with 10-second timeout constraint
        start_time = time.time()
        timeout = 10

        while True:
            container.reload()
            if container.status == 'exited':
                break
            if time.time() - start_time > timeout:
                container.kill()
                container.remove(force=True)
                return {"stdout": "", "stderr": "Execution timed out (10s limit).", "returncode": 124}
            time.sleep(0.2)

        # Extract exit code
        result = container.wait()
        returncode = result.get('StatusCode', 1)

        # Capture logs
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

        # Cleanup
        container.remove()

        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode
        }
    except docker.errors.DockerException as e:
        return {"stdout": "", "stderr": f"Docker error: {str(e)}\nIs Docker running?", "returncode": 1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": 1}
