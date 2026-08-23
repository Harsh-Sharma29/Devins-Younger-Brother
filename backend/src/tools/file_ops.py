import os
import tempfile
import shutil
import docker
import time
from typing import Dict, Optional
import threading
from src.core.pubsub import publish
from src.core.types import SandboxExecutionResult, ErrorTaxonomy

def sandbox_workspace_dir() -> str:
    override = os.getenv("AUTOFORGE_SANDBOX_DIR", "").strip()
    if override:
        workspace_dir = os.path.abspath(override)
    else:
        workspace_dir = os.path.join(tempfile.gettempdir(), "autoforge_sandbox")
    os.makedirs(workspace_dir, exist_ok=True)
    return workspace_dir

def clear_sandbox_workspace() -> None:
    workspace_dir = sandbox_workspace_dir()
    for item in os.listdir(workspace_dir):
        item_path = os.path.join(workspace_dir, item)
        try:
            if os.path.isfile(item_path): os.remove(item_path)
            elif os.path.isdir(item_path): shutil.rmtree(item_path)
        except OSError: pass

def write_code_to_disk(filename: str, code: str) -> str:
    workspace_dir = sandbox_workspace_dir()
    file_path = os.path.join(workspace_dir, filename)
    parent = os.path.dirname(file_path)
    if parent and not os.path.exists(parent): os.makedirs(parent, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f: f.write(code)
    return file_path

def write_workspace_to_disk(files: Dict[str, str]) -> str:
    workspace_dir = sandbox_workspace_dir()
    for filename, content in files.items(): write_code_to_disk(filename, content)
    return workspace_dir

def execute_python_code(
    filename: str,
    *,
    entry_file: Optional[str] = None,
    workspace_files: Optional[Dict[str, str]] = None,
    thread_id: Optional[str] = None,
    runtime: str = 'Python',
) -> dict:
    clear_sandbox_workspace()
    workspace_dir = sandbox_workspace_dir()
    if workspace_files: write_workspace_to_disk(workspace_files)
    run_file = entry_file or filename
    file_path = os.path.join(workspace_dir, run_file)

    if not os.path.exists(file_path):
        return SandboxExecutionResult(status="failed", error_type=ErrorTaxonomy.ARTIFACT_CONTRACT_ERROR, exit_code=1, stdout="", stderr=f"File not found: {file_path}", duration_ms=0, container_id="", safety_status="failed").dict()

    try:
        client = docker.from_env()
        requirements_path = os.path.join(workspace_dir, "requirements.txt")
        if runtime == "Browser":
            command = "python -m http.server 8000 -d /sandbox & sleep 2 && curl -s http://localhost:8000/index.html | head -n 10 && echo '\n[Runtime Test] Browser assets served successfully.'"
            exec_command = ["sh", "-c", command]
        else:
            if os.path.exists(requirements_path):
                req_content = open(requirements_path).read().lower()
                if "fastapi" in req_content and "uvicorn" in req_content:
                    command = f"pip install --quiet -r /sandbox/requirements.txt 2>/dev/null; uvicorn {run_file.replace('.py', '')}:app --app-dir /sandbox --host 0.0.0.0 --port 8000 & sleep 5 && curl -s http://localhost:8000/docs > /dev/null && echo '\n[Runtime Test] FastAPI server started and responded.' || {{ echo '\n[Runtime Test] FastAPI failed.'; exit 1; }}"
                else:
                    command = f"pip install --quiet -r /sandbox/requirements.txt 2>/dev/null; python -u /sandbox/{run_file}"
                exec_command = ["sh", "-c", command]
            else:
                exec_command = ["python", "-u", f"/sandbox/{run_file}"]

        volume_source = os.getenv("AUTOFORGE_DOCKER_VOLUME", workspace_dir)
        
        container = client.containers.run(
            image="python:3.11-slim",
            command=exec_command,
            volumes={volume_source: {'bind': '/sandbox', 'mode': 'ro'}},
            detach=True,
            mem_limit="256m",
            cpu_period=100000,
            cpu_quota=50000,
            pids_limit=50,
            network_mode="bridge",
            read_only=True
        )

        stdout_acc = []
        stderr_acc = []
        if thread_id:
            publish(thread_id, f"[Sandbox] Executing {run_file}...\n")
            def stream_logs():
                try:
                    for out, err in container.logs(stream=True, follow=True, demux=True):
                        if out:
                            chunk = out.decode("utf-8", errors="replace")
                            stdout_acc.append(chunk)
                            publish(thread_id, chunk)
                        if err:
                            chunk = err.decode("utf-8", errors="replace")
                            stderr_acc.append(chunk)
                            publish(thread_id, chunk)
                except Exception: pass
            t = threading.Thread(target=stream_logs, daemon=True)
            t.start()

        start_time = time.time()
        timeout = 60
        is_timeout = False

        while True:
            container.reload()
            if container.status == 'exited':
                break
            if time.time() - start_time > timeout:
                is_timeout = True
                container.kill()
                break
            time.sleep(0.2)
            
        duration = int((time.time() - start_time) * 1000)

        container.reload()
        oom_killed = container.attrs.get("State", {}).get("OOMKilled", False)
        exit_code = container.attrs.get("State", {}).get("ExitCode", 1)

        if not thread_id:
            stdout_str = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr_str = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        else:
            t.join(timeout=1.0)
            stdout_str = "".join(stdout_acc)
            stderr_str = "".join(stderr_acc)

        container.remove(force=True)

        err_type = ErrorTaxonomy.NONE
        status = "passed"
        safety = "passed"

        if is_timeout:
            err_type = ErrorTaxonomy.TIMEOUT
            status = "failed"
            stderr_str += "\n[Sandbox] Execution timed out (60s limit)."
        elif oom_killed:
            err_type = ErrorTaxonomy.MEMORY_LIMIT
            status = "failed"
            stderr_str += "\n[Sandbox] Process killed due to memory limit (256MB)."
        elif exit_code != 0:
            err_type = ErrorTaxonomy.RUNTIME_ERROR
            status = "failed"

        return SandboxExecutionResult(
            status=status,
            error_type=err_type,
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_ms=duration,
            container_id=container.id[:12],
            safety_status=safety
        ).dict()

    except docker.errors.DockerException as e:
        return SandboxExecutionResult(status="failed", error_type=ErrorTaxonomy.DOCKER_ERROR, exit_code=1, stdout="", stderr=f"Docker error: {str(e)}\nIs Docker running?", duration_ms=0, container_id="", safety_status="passed").dict()
    except Exception as e:
        return SandboxExecutionResult(status="failed", error_type=ErrorTaxonomy.INFRASTRUCTURE_ERROR, exit_code=1, stdout="", stderr=str(e), duration_ms=0, container_id="", safety_status="passed").dict()
