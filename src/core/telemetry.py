"""
Session telemetry helpers for the Streamlit dashboard.
Captures real system metrics (CPU, RAM) and token throughput estimates.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def _real_cpu_pct() -> float:
    """Return actual host CPU usage; gracefully degrade if psutil unavailable."""
    if _PSUTIL_AVAILABLE:
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            pass
    return 0.0


def _real_ram_pct() -> float:
    """Return actual host RAM usage; gracefully degrade if psutil unavailable."""
    if _PSUTIL_AVAILABLE:
        try:
            return psutil.virtual_memory().percent
        except Exception:
            pass
    return 0.0


def default_telemetry() -> Dict[str, Any]:
    return {
        "total_tokens": 0,
        "latency_ms": 0,
        "cpu_pct": _real_cpu_pct(),
        "ram_pct": _real_ram_pct(),
        "resource_index": 0.0,
        "_step_start_ts": time.time(),
    }


def estimate_tokens(*chunks: Optional[str]) -> int:
    combined = "".join(c for c in chunks if c)
    if not combined.strip():
        return 0
    return max(1, len(combined) // 4)


def node_transition_line(node_name: str, status: str = "Active") -> str:
    """Produce professional telemetry strings for LangGraph node transitions."""
    ts = time.strftime("%H:%M:%S")
    
    # Map node names to clean labels
    mapping = {
        "coder_agent": "Coder",
        "terminal_agent": "Terminal",
        "debugger_agent": "Debugger",
        "planner_agent": "Planner",
        "router_node": "Router",
        "validator_node": "Validator",
        "research_agent": "Research",
        "knowledge_agent": "Knowledge"
    }
    
    clean_name = mapping.get(node_name, node_name.replace("_agent", "").replace("_node", "").replace("_", " ").title())
    return f"[{ts}] Node: {clean_name} → {status}"


def tick_telemetry(
    telemetry: Dict[str, Any],
    *,
    log_line: str = "",
    code: str = "",
    step_index: int = 0,
    final: bool = False,
) -> Dict[str, Any]:
    """Advance telemetry counters for one pipeline step using real system data."""
    tel = dict(telemetry or default_telemetry())
    tel["total_tokens"] = int(tel.get("total_tokens", 0)) + estimate_tokens(log_line, code)

    # Real latency: wall-clock delta since last step
    now = time.time()
    prev_ts = float(tel.get("_step_start_ts", now))
    tel["latency_ms"] = int((now - prev_ts) * 1000)
    tel["_step_start_ts"] = now

    # Real system metrics
    tel["cpu_pct"] = round(_real_cpu_pct(), 1)
    tel["ram_pct"] = round(_real_ram_pct(), 1)
    tel["resource_index"] = round((tel["cpu_pct"] + tel["ram_pct"]) / 2.0, 1)
    return tel


def telemetry_from_state(dashboard_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive telemetry snapshot from a LangGraph result using real system data."""
    if not dashboard_state:
        return default_telemetry()

    logs = dashboard_state.get("pipeline_logs") or []
    code = dashboard_state.get("code_buffer") or ""
    term = dashboard_state.get("terminal_output") or ""
    tokens = estimate_tokens("\n".join(logs), code, term)

    cpu = _real_cpu_pct()
    ram = _real_ram_pct()

    return {
        "total_tokens": tokens,
        "latency_ms": dashboard_state.get("latency_ms", 0),
        "cpu_pct": round(cpu, 1),
        "ram_pct": round(ram, 1),
        "resource_index": round((cpu + ram) / 2.0, 1),
    }
