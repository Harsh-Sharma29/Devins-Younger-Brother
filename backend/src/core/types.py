from enum import Enum
from typing import List, Literal, Optional, Any, Dict
from pydantic import BaseModel, Field

class PipelineStatus(str, Enum):
    SUCCESS = "PIPELINE_SUCCESS"
    FAILED = "PIPELINE_FAILED"
    PARTIAL = "PIPELINE_PARTIAL"
    REPAIR_EXHAUSTED = "REPAIR_EXHAUSTED"
    IN_PROGRESS = "IN_PROGRESS"

class ErrorTaxonomy(str, Enum):
    PLANNING_ERROR = "PLANNING_ERROR"
    STRUCTURED_OUTPUT_ERROR = "STRUCTURED_OUTPUT_ERROR"
    ARTIFACT_CONTRACT_ERROR = "ARTIFACT_CONTRACT_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    CPU_LIMIT = "CPU_LIMIT"
    PROCESS_LIMIT = "PROCESS_LIMIT"
    DISK_LIMIT = "DISK_LIMIT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SANDBOX_RUNTIME_ERROR = "SANDBOX_RUNTIME_ERROR"
    DOCKER_ERROR = "DOCKER_ERROR"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    NONE = "NONE"

class ArtifactContract(BaseModel):
    task_type: str = Field(description="e.g., cli_script, web_app, api")
    runtime: Literal["Browser", "Python", "Unknown"] = Field(description="Target runtime environment")
    artifacts: List[str] = Field(description="List of all expected file names, e.g. ['fib.py', 'utils.py']")
    entry_file: str = Field(description="The primary entry file to execute or serve, e.g. 'fib.py'")
    requirements: List[str] = Field(description="Clear breakdown of features the code must implement")

class ValidatorFeedback(BaseModel):
    error_type: ErrorTaxonomy
    expected_path: Optional[str]
    message: str
    required_action: str

class DebuggerAction(BaseModel):
    action: Literal["rewrite_file", "patch_file", "create_file", "delete_file", "no_change", "abort"]
    path: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    reason: str

class SandboxExecutionResult(BaseModel):
    status: Literal["passed", "failed"]
    error_type: ErrorTaxonomy
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    container_id: str
    safety_status: Literal["passed", "failed"]
