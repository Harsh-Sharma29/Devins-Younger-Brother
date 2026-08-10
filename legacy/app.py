"""
Devin's Younger Brother — Pro IDE Workbench (Frontend)
Pure Streamlit frontend. Communicates with the FastAPI backend via HTTP/SSE.
Multi-file workspace · Real-time telemetry · Monaco-style code editor.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import uuid
from typing import Any, Dict, Optional

import requests

if not hasattr(importlib.metadata, "packages_distributions"):
    def mock_packages_distributions():
        return {}
    importlib.metadata.packages_distributions = mock_packages_distributions

import streamlit as st
from streamlit_ace import st_ace
from dotenv import load_dotenv

load_dotenv()

# ─── API CONFIG ─────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("DYB_API_URL", "http://localhost:8000").rstrip("/")
DEFAULT_RECURSION_LIMIT = 50

st.set_page_config(
    page_title="Devin's Younger Brother — Pro IDE",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CUSTOM CSS ─────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');
    :root {
        --bg-deep: #0a0a0f; --bg-panel: #111117; --bg-elevated: #1a1a22;
        --border-subtle: #23232e; --border-active: #2d5a8a;
        --text-primary: #e2e4e9; --text-muted: #6b7280; --text-dim: #4b5563;
        --accent-cyan: #00b4d8; --accent-blue: #3b82f6; --accent-emerald: #10b981;
        --accent-glow: rgba(0, 180, 216, 0.2);
        --terminal-bg: #000000; --terminal-green: #39ff14; --terminal-white: #d1d5db;
    }
    .stApp {
        background: var(--bg-deep);
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d14 0%, #0a0a0f 100%);
        border-right: 1px solid var(--border-subtle);
    }
    h1, h2, h3, h4, p, label, span, .stMarkdown { color: var(--text-primary); }
    .stTextArea textarea {
        background: var(--bg-elevated) !important; color: var(--text-primary) !important;
        border: 1px solid var(--border-subtle) !important; border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important; font-size: 0.82rem !important;
    }
    div[data-testid="stButton"] button {
        width: 100%; min-height: 3rem; font-weight: 600 !important; border-radius: 8px !important;
        border: 1px solid var(--accent-cyan) !important;
        background: linear-gradient(135deg, #0c4a6e 0%, #0369a1 50%, #1e40af 100%) !important;
        color: #fff !important; box-shadow: 0 0 16px var(--accent-glow) !important;
        transition: all 0.2s ease;
    }
    div[data-testid="stButton"] button:hover {
        box-shadow: 0 0 28px rgba(0, 180, 216, 0.4) !important;
        transform: translateY(-1px);
    }
    /* IDE Header */
    .ide-header {
        padding: 0.4rem 0 1rem;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 0.75rem;
        display: flex; align-items: center; gap: 0.75rem;
    }
    .ide-title {
        font-size: 1.5rem; font-weight: 700;
        background: linear-gradient(90deg, #00b4d8, #3b82f6, #8b5cf6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .ide-mode-badge {
        display: inline-flex; align-items: center; gap: 0.35rem;
        padding: 0.2rem 0.65rem; border-radius: 999px;
        background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3);
        font-size: 0.7rem; font-weight: 600; color: #34d399;
        letter-spacing: 0.04em;
    }
    .ide-mode-dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: #34d399;
        animation: pulse-dot 2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }
    /* Panel headers */
    .panel-header {
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--text-muted);
        padding: 0.5rem 0.75rem; margin-bottom: 0.5rem;
        border-bottom: 1px solid var(--border-subtle);
        display: flex; align-items: center; gap: 0.5rem;
    }
    .panel-header-icon { font-size: 0.85rem; }
    /* File tab bar */
    .file-tabs {
        display: flex; gap: 0; overflow-x: auto;
        border-bottom: 1px solid var(--border-subtle);
        background: var(--bg-panel);
        padding: 0 0.5rem;
    }
    .file-tab {
        padding: 0.45rem 0.85rem; font-size: 0.72rem; font-weight: 500;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-muted); cursor: pointer;
        border-bottom: 2px solid transparent;
        transition: all 0.15s ease; white-space: nowrap;
    }
    .file-tab:hover { color: var(--text-primary); background: var(--bg-elevated); }
    .file-tab-active {
        color: var(--accent-cyan) !important;
        border-bottom-color: var(--accent-cyan) !important;
        background: var(--bg-elevated);
    }
    /* Code workspace empty state */
    .code-empty {
        background: var(--bg-panel); border: 1px dashed var(--border-subtle);
        border-radius: 8px; padding: 3rem 1.5rem; text-align: center;
        color: var(--text-dim); font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
    }
    /* Terminal */
    .ide-terminal {
        background: var(--terminal-bg);
        border: 1px solid #1a1a1a; border-radius: 8px;
        padding: 0.75rem 1rem;
        min-height: 460px; max-height: 560px; overflow-y: auto;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.75rem; line-height: 1.6;
        color: var(--terminal-green);
        box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.8);
        white-space: pre-wrap;
    }
    .ide-terminal .sys-msg { color: var(--terminal-white); }
    .ide-terminal .err-msg { color: #f87171; }
    .ide-terminal .node-msg { color: #60a5fa; }
    /* Banners */
    .banner-ok {
        background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 8px; padding: 0.65rem 1rem; margin-bottom: 0.75rem;
        color: #6ee7b7; font-size: 0.82rem;
    }
    .banner-warn {
        background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 8px; padding: 0.65rem 1rem; margin-bottom: 0.75rem;
        color: #fbbf24; font-size: 0.82rem;
    }
    .banner-error {
        background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 8px; padding: 0.65rem 1rem; margin-bottom: 0.75rem;
        color: #fca5a5; font-size: 0.82rem;
    }
    /* Telemetry cards */
    .tel-card-sidebar {
        background: var(--bg-elevated); border: 1px solid var(--border-subtle);
        border-radius: 8px; padding: 0.6rem 0.75rem; margin-bottom: 0.5rem;
    }
    .tel-label { font-size: 0.62rem; color: var(--text-muted); margin-bottom: 0.2rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .tel-value { font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 600; color: var(--accent-cyan); }
    .tel-sub { font-size: 0.6rem; color: var(--text-dim); margin-top: 0.15rem; }
    /* Status indicators */
    .status-connected { color: #34d399; }
    .status-fallback { color: #fbbf24; }
    .status-error { color: #f87171; }
    .status-dot {
        display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 0.4rem;
    }
    .dot-green { background: #34d399; box-shadow: 0 0 6px rgba(52, 211, 153, 0.5); }
    .dot-yellow { background: #fbbf24; box-shadow: 0 0 6px rgba(251, 191, 36, 0.5); }
    .dot-red { background: #f87171; box-shadow: 0 0 6px rgba(248, 113, 113, 0.5); }
    /* Sidebar section */
    .sidebar-section {
        background: var(--bg-elevated); border: 1px solid var(--border-subtle);
        border-radius: 8px; padding: 0.75rem; margin-bottom: 0.75rem;
    }
    .sidebar-section-title {
        font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 0.5rem;
    }
    /* Visual Pipeline Graph */
    .pipeline-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--bg-panel);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .pipeline-node {
        flex: 1;
        text-align: center;
        padding: 0.5rem 0.25rem;
        border-radius: 8px;
        background: var(--bg-elevated);
        border: 1px solid var(--border-subtle);
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        font-weight: 500;
        transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        opacity: 0.55;
    }
    .pipeline-arrow {
        color: var(--text-dim);
        font-size: 1rem;
        padding: 0 0.5rem;
        user-select: none;
    }
    .pipeline-node.node-active {
        color: #ffffff !important;
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border-color: var(--accent-cyan) !important;
        transform: scale(1.08);
        box-shadow: 0 0 18px rgba(0, 180, 216, 0.6), inset 0 0 6px rgba(0, 180, 216, 0.3) !important;
        font-weight: 700;
        z-index: 10;
        opacity: 1.0 !important;
    }
    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DEFAULT_PROMPT = (
    "Create a simple text file named test.txt with the content "
    "'Hello from Devin\\'s Younger Brother'."
)


# ─── API CLIENT ─────────────────────────────────────────────────────────────────
def _fetch_health() -> Dict[str, Any]:
    """GET /api/v1/health — returns Postgres status, API keys, telemetry."""
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {
            "postgres": {"status": "error", "label": f"API unreachable: {exc}"},
            "gemini_ok": False,
            "hf_ok": False,
            "using_fallback": True,
            "telemetry": {"cpu_pct": 0, "ram_pct": 0, "total_tokens": 0, "latency_ms": 0},
        }


def _fetch_history(thread_id: str) -> list:
    """GET /api/v1/history/{thread_id} — returns the conversation history."""
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/history/{thread_id}", timeout=5)
        resp.raise_for_status()
        return resp.json().get("conversation_history") or []
    except Exception:
        return []


def _create_session() -> str:
    """POST /api/v1/session/new — returns a backend-generated thread_id."""
    try:
        resp = requests.post(f"{API_BASE_URL}/api/v1/session/new", timeout=5)
        resp.raise_for_status()
        return resp.json().get("thread_id", str(uuid.uuid4()))
    except Exception:
        return str(uuid.uuid4())


def _default_telemetry() -> Dict[str, Any]:
    """Local fallback telemetry defaults for session state init."""
    return {"total_tokens": 0, "latency_ms": 0, "cpu_pct": 0.0, "ram_pct": 0.0, "resource_index": 0.0}


# ─── SESSION STATE ──────────────────────────────────────────────────────────────
def _init_session() -> None:
    defaults = {
        "dashboard_state": None,
        "console_logs": "",
        "pipeline_error": None,
        "last_run_ok": False,
        "telemetry": _default_telemetry(),
        "thread_id": str(uuid.uuid4()),
        "active_file": "main.py",
        "active_node": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _append_console(line: str) -> str:
    current = (st.session_state.get("console_logs") or "").strip()
    st.session_state["console_logs"] = f"{current}\n{line}".strip() if current else line
    return st.session_state["console_logs"]


def _get_telemetry() -> dict:
    return dict(st.session_state.get("telemetry") or _default_telemetry())


def _render_pipeline_graph(active_node_name: Optional[str], *, container: Any) -> None:
    """Render a visual horizontal pipeline graph highlighting the active node."""
    node_mapping = {
        "router_node": "Router",
        "planner_agent": "Planner",
        "coder_model": "Coder",
        "coder_tools": "Coder",
        "coder_finalize": "Coder",
        "coder_agent": "Coder",
        "validator_node": "Validator",
        "terminal_agent": "Sandbox",
        "debugger_agent": "Debugger",
    }
    
    blocks = ["Router", "Planner", "Coder", "Validator", "Sandbox", "Debugger"]
    active_block = node_mapping.get(active_node_name) if active_node_name else None
    
    html = '<div class="pipeline-container">'
    for i, block in enumerate(blocks):
        is_active = (block == active_block)
        active_class = "node-active" if is_active else ""
        
        icon = ""
        if block == "Router": icon = "🧭 "
        elif block == "Planner": icon = "📋 "
        elif block == "Coder": icon = "💻 "
        elif block == "Validator": icon = "🛡️ "
        elif block == "Sandbox": icon = "📦 "
        elif block == "Debugger": icon = "🪲 "
        
        html += f'<div class="pipeline-node {active_class}">{icon}{block}</div>'
        if i < len(blocks) - 1:
            html += '<div class="pipeline-arrow">➔</div>'
    html += '</div>'
    
    container.markdown(html, unsafe_allow_html=True)


# ─── RENDER HELPERS ─────────────────────────────────────────────────────────────
def _render_telemetry_sidebar(container: Any) -> None:
    tel = _get_telemetry()
    tokens = int(tel.get("total_tokens", 0))
    latency = int(tel.get("latency_ms", 0))
    cpu = float(tel.get("cpu_pct", 0.0))
    ram = float(tel.get("ram_pct", 0.0))

    html = f"""
    <div class="tel-card-sidebar">
        <div class="tel-label">Tokens Throughput</div>
        <div class="tel-value">{tokens:,}</div>
        <div class="tel-sub">Cumulative tokens generated</div>
    </div>
    <div class="tel-card-sidebar">
        <div class="tel-label">Latency Delta</div>
        <div class="tel-value">{latency} ms</div>
        <div class="tel-sub">Step execution wall-clock</div>
    </div>
    <div class="tel-card-sidebar">
        <div class="tel-label">CPU Usage</div>
        <div class="tel-value">{cpu:.1f}%</div>
        <div class="tel-sub">Backend host CPU</div>
    </div>
    <div class="tel-card-sidebar">
        <div class="tel-label">RAM Usage</div>
        <div class="tel-value">{ram:.1f}%</div>
        <div class="tel-sub">Backend host memory</div>
    </div>
    """
    container.markdown(html, unsafe_allow_html=True)


def _render_terminal(text: str, *, container: Optional[Any] = None) -> None:
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    html = f'<div class="ide-terminal">{safe}</div>'
    if container is not None:
        container.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _render_code_editor(code: str, *, container: Optional[Any] = None, readonly: bool = False) -> None:
    """Render the Ace code editor with syntax highlighting."""
    target = container if container is not None else st
    if code and code.strip():
        target.empty()
        with target.container():
            active_file = st.session_state.get('active_file', 'main.py')
            editor_key = f"ace_editor_{active_file}_{uuid.uuid4().hex[:8]}" if readonly else f"ace_editor_{active_file}_stable"
            updated_code = st_ace(
                value=code,
                language="python",
                theme="monokai",
                font_size=13,
                show_gutter=True,
                show_print_margin=False,
                wrap=True,
                auto_update=True,
                readonly=readonly,
                min_lines=28,
                max_lines=42,
                key=editor_key,
            )
            # If the user edited the code, save it back
            if not readonly and updated_code != code:
                active_file = st.session_state.get("active_file", "main.py")
                state = st.session_state.get("dashboard_state")
                if state and isinstance(state, dict):
                    if "workspace_files" not in state:
                        state["workspace_files"] = {}
                    state["workspace_files"][active_file] = updated_code
                    state["code_buffer"] = updated_code
                st.rerun()
    else:
        target.markdown(
            '<div class="code-empty">// Awaiting generated code from Coder agent…</div>',
            unsafe_allow_html=True,
        )


def _render_file_tabs(workspace_files: Dict[str, str], active_file: str, *, container: Optional[Any] = None) -> None:
    """Render clickable file tabs above the editor."""
    if not workspace_files:
        return
    tabs_html = '<div class="file-tabs">'
    for fname in sorted(workspace_files.keys()):
        cls = "file-tab file-tab-active" if fname == active_file else "file-tab"
        tabs_html += f'<div class="{cls}">{fname}</div>'
    tabs_html += '</div>'
    target = container if container is not None else st
    target.markdown(tabs_html, unsafe_allow_html=True)


# ─── SSE PIPELINE EXECUTION ────────────────────────────────────────────────────
def _parse_sse_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single SSE line into {event, data} or None."""
    line = line.strip()
    if line.startswith("event:"):
        return {"event": line[len("event:"):].strip()}
    if line.startswith("data:"):
        return {"data": line[len("data:"):].strip()}
    return None


def _stream_from_api(
    prompt: str,
    thread_id: str,
    recursion_limit: int,
    *,
    terminal_slot: Any,
    code_slot: Any,
    telemetry_slot: Any,
    file_tabs_slot: Any,
    pipeline_slot: Any,
) -> Dict[str, Any]:
    """POST to /api/v1/execute and consume SSE events, rendering updates live."""

    _append_console("[System] LangGraph stream started · Live Production Mode")
    _render_terminal(st.session_state["console_logs"], container=terminal_slot)

    payload = {
        "prompt": prompt,
        "thread_id": thread_id,
        "recursion_limit": recursion_limit,
    }

    final_state: Dict[str, Any] = {}

    try:
        with requests.post(
            f"{API_BASE_URL}/api/v1/execute",
            json=payload,
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()

            current_event = ""
            data_buffer = ""

            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = raw_line.strip()

                # SSE blank line = end of event
                if not line:
                    if current_event and data_buffer:
                        try:
                            data = json.loads(data_buffer)
                        except json.JSONDecodeError:
                            data = {}

                        if current_event == "node_update":
                            # Render transition line
                            transition = data.get("transition", "")
                            if transition:
                                _append_console(transition)

                            # Render new pipeline logs
                            for log_line in data.get("new_logs", []):
                                _append_console(str(log_line))

                            # Render terminal output delta
                            term_delta = data.get("terminal_output_delta", "")
                            if term_delta:
                                _append_console(term_delta)

                            # Update active visual node
                            active_node = data.get("node_name")
                            if active_node:
                                st.session_state["active_node"] = active_node
                                _render_pipeline_graph(active_node, container=pipeline_slot)

                            # Update telemetry
                            tel = data.get("telemetry")
                            if tel:
                                st.session_state["telemetry"] = tel

                            # Update code editor
                            workspace = data.get("workspace_files") or {}
                            active = data.get("active_file") or st.session_state.get("active_file", "main.py")
                            code = data.get("code_buffer") or ""
                            _render_file_tabs(workspace, active, container=file_tabs_slot)
                            _render_code_editor(code, container=code_slot, readonly=True)

                            # Render updated telemetry + terminal
                            _render_telemetry_sidebar(container=telemetry_slot)
                            _render_terminal(st.session_state["console_logs"], container=terminal_slot)

                        elif current_event == "complete":
                            final_state = data
                            tel = data.get("telemetry")
                            if tel:
                                st.session_state["telemetry"] = tel

                        elif current_event == "error":
                            error_msg = data.get("error", "Unknown API error")
                            _append_console(f"[System] Pipeline error: {error_msg}")
                            _render_terminal(st.session_state["console_logs"], container=terminal_slot)
                            return {
                                "detected_errors": [error_msg],
                                "is_verified": False,
                            }

                    current_event = ""
                    data_buffer = ""
                    continue

                if line.startswith("event:"):
                    current_event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_buffer += line[len("data:"):].strip()

    except requests.exceptions.ConnectionError:
        error_msg = f"Cannot connect to API at {API_BASE_URL}. Is the FastAPI server running?"
        _append_console(f"[System] {error_msg}")
        _render_terminal(st.session_state["console_logs"], container=terminal_slot)
        return {"detected_errors": [error_msg], "is_verified": False}
    except requests.exceptions.Timeout:
        error_msg = "API request timed out (300s limit)."
        _append_console(f"[System] {error_msg}")
        _render_terminal(st.session_state["console_logs"], container=terminal_slot)
        return {"detected_errors": [error_msg], "is_verified": False}
    except Exception as exc:
        error_msg = f"API communication error: {exc}"
        _append_console(f"[System] {error_msg}")
        _render_terminal(st.session_state["console_logs"], container=terminal_slot)
        return {"detected_errors": [str(exc)], "is_verified": False}

    return final_state


# ─── INITIALIZE ─────────────────────────────────────────────────────────────────
_init_session()

# Fetch backend health for status panel (cached per page load)
_health = _fetch_health()

# ─── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.25rem 0 0.75rem;">
            <p class="ide-title" style="font-size:1.3rem; margin:0;">⚡ Control Center</p>
            <p style="color: var(--text-muted); font-size: 0.72rem; margin-top: 0.15rem;">
                Devin's Younger Brother · Pro IDE
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("pipeline_form", clear_on_submit=False, border=False):
        user_prompt = st.text_area(
            "User Prompt",
            value=st.session_state.get("last_user_prompt", DEFAULT_PROMPT),
            height=200,
            label_visibility="collapsed",
            key="user_prompt_input",
        )

        recursion_limit = st.slider(
            "LangGraph recursion_limit",
            min_value=10,
            max_value=50,
            value=DEFAULT_RECURSION_LIMIT,
            step=5,
        )

        execute_clicked = st.form_submit_button(
            "🚀 Execute Pipeline",
            type="primary",
            use_container_width=True,
        )

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state["thread_id"] = _create_session()
        st.session_state["dashboard_state"] = None
        st.session_state["console_logs"] = ""
        st.session_state["pipeline_error"] = None
        st.session_state["last_run_ok"] = False
        st.session_state["last_user_prompt"] = DEFAULT_PROMPT
        st.session_state["telemetry"] = _default_telemetry()
        st.session_state["active_file"] = "main.py"
        st.session_state["active_node"] = None
        st.rerun()

    st.markdown("---")

    # ── System Status (from API health endpoint) ──
    gemini_ok = _health.get("gemini_ok", False)
    hf_ok = _health.get("hf_ok", False)
    api_reachable = _health.get("postgres", {}).get("status") != "error" or "API unreachable" not in _health.get("postgres", {}).get("label", "")

    st.markdown(
        f"""
        <div class="sidebar-section">
            <div class="sidebar-section-title">API Connections</div>
            <div style="font-size: 0.78rem; line-height: 1.8;">
                <span class="status-dot dot-{'green' if api_reachable else 'red'}"></span>
                Backend API: <strong>{'Connected' if api_reachable else 'Unreachable'}</strong><br>
                <span class="status-dot dot-{'green' if gemini_ok else 'red'}"></span>
                Gemini API: <strong>{'Loaded' if gemini_ok else 'Missing'}</strong><br>
                <span class="status-dot dot-{'green' if hf_ok else 'red'}"></span>
                HF Failover: <strong>{'Active' if hf_ok else 'Missing'}</strong><br>
                <span style="color: var(--text-dim);">Mode:</span>
                <strong style="color: var(--accent-emerald);">Live Production</strong><br>
                <span style="color: var(--text-dim);">Thread:</span>
                <code style="font-size: 0.68rem;">{st.session_state['thread_id'][:12]}…</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ─── MAIN IDE LAYOUT ───────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="ide-header">
        <p class="ide-title">Devin's Younger Brother</p>
        <div class="ide-mode-badge">
            <div class="ide-mode-dot"></div>
            LIVE PRODUCTION
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

banner_slot = st.empty()
pipeline_slot = st.empty()
_render_pipeline_graph(st.session_state.get("active_node"), container=pipeline_slot)

# 3-Pane IDE Layout: Status | Editor | Terminal
col_status, col_editor, col_terminal = st.columns([2, 5, 3], gap="medium")

# 1. Left (20%): Telemetry, Postgres status, file selector
with col_status:
    st.markdown(
        '<div class="panel-header"><span class="panel-header-icon">📊</span> Telemetry & Status</div>',
        unsafe_allow_html=True,
    )

    # Postgres status card (from health API)
    pg_health = _health.get("postgres", {"status": "disconnected", "label": "Unknown"})
    pg_status = pg_health.get("status", "disconnected")
    pg_label = pg_health.get("label", "Unknown")

    if pg_status == "connected":
        pg_icon, pg_color = "🟢", "green"
    elif pg_status == "fallback":
        pg_icon, pg_color = "🟡", "yellow"
    else:
        pg_icon, pg_color = "🔴", "red"

    st.markdown(
        f"""
        <div class="sidebar-section">
            <div class="sidebar-section-title">Database Status</div>
            <div style="font-size: 0.8rem; line-height: 1.8;">
                <span class="status-dot dot-{pg_color}"></span>
                Postgres: <strong>{pg_icon} {pg_label}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Live Telemetry Slot
    # Seed from health API telemetry on initial load
    if not st.session_state.get("dashboard_state"):
        health_tel = _health.get("telemetry", {})
        if health_tel:
            current_tel = _get_telemetry()
            current_tel["cpu_pct"] = health_tel.get("cpu_pct", current_tel.get("cpu_pct", 0))
            current_tel["ram_pct"] = health_tel.get("ram_pct", current_tel.get("ram_pct", 0))
            st.session_state["telemetry"] = current_tel

    status_telemetry_slot = st.empty()
    _render_telemetry_sidebar(status_telemetry_slot)

    # Multi-file Selector
    st.markdown(
        '<div class="panel-header" style="margin-top: 0.75rem;"><span class="panel-header-icon">📁</span> Workspace Files</div>',
        unsafe_allow_html=True,
    )

    state = st.session_state.get("dashboard_state")
    workspace = (state or {}).get("workspace_files") or {}
    active = st.session_state.get("active_file", "main.py")

    file_names = sorted(workspace.keys()) if workspace else ["main.py"]
    if active not in file_names:
        active = file_names[0]

    # File selector dropdown
    selected_file = st.selectbox(
        "Active File Dropdown",
        file_names,
        index=file_names.index(active) if active in file_names else 0,
        label_visibility="collapsed",
        key="file_selector_dropdown",
    )
    if selected_file != active:
        st.session_state["active_file"] = selected_file
        st.rerun()

    # Visual list explorer of files
    file_list_slot = st.empty()
    if workspace:
        file_list_html = '<div class="sidebar-section" style="margin-top: 0.5rem;">'
        for fname in file_names:
            icon = "🐍" if fname.endswith(".py") else "📄"
            weight = "600" if fname == active else "400"
            color = "var(--accent-cyan)" if fname == active else "var(--text-muted)"
            file_list_html += f'<div style="font-size: 0.75rem; padding: 0.2rem 0; color: {color}; font-weight: {weight};">{icon} {fname}</div>'
        file_list_html += '</div>'
        file_list_slot.markdown(file_list_html, unsafe_allow_html=True)
    else:
        file_list_slot.markdown(
            '<div style="font-size: 0.75rem; color: var(--text-dim); padding: 0.5rem;">No files generated yet</div>',
            unsafe_allow_html=True,
        )

    # Chat history section using st.chat_message
    st.markdown(
        '<div class="panel-header" style="margin-top: 0.75rem;"><span class="panel-header-icon">💬</span> Chat History</div>',
        unsafe_allow_html=True,
    )
    history = _fetch_history(st.session_state["thread_id"])
    if history:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(f"<span style='font-size: 0.78rem;'>{msg['content']}</span>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="font-size: 0.75rem; color: var(--text-dim); padding: 0.5rem;">No conversation history yet.</div>',
            unsafe_allow_html=True,
        )

# 2. Center (50%): Monaco-style st_ace editor
with col_editor:
    st.markdown(
        '<div class="panel-header"><span class="panel-header-icon">💻</span> Code Workspace</div>',
        unsafe_allow_html=True,
    )
    file_tabs_slot = st.empty()
    code_slot = st.empty()

# 3. Right (30%): Live Terminal (true black, Consolas, light green text)
with col_terminal:
    st.markdown(
        '<div class="panel-header"><span class="panel-header-icon">📟</span> Live Terminal</div>',
        unsafe_allow_html=True,
    )
    terminal_slot = st.empty()


# ─── EXECUTION ROUTING ─────────────────────────────────────────────────────────
if execute_clicked:
    prompt_text = (user_prompt or "").strip()
    st.session_state["last_user_prompt"] = prompt_text

    if not prompt_text:
        st.warning("Please enter a user prompt before executing the pipeline.")
    else:
        st.session_state["dashboard_state"] = None
        st.session_state["console_logs"] = (
            "🚀 Pipeline starting…\n"
            f"[System] user_prompt accepted ({len(prompt_text)} chars)\n"
            f"[System] prompt preview: {prompt_text[:120]}{'…' if len(prompt_text) > 120 else ''}\n"
            f"[System] thread_id={st.session_state['thread_id']}\n"
            f"[System] Mode: Live Production · API: {API_BASE_URL}"
        )
        st.session_state["telemetry"] = _default_telemetry()
        st.session_state["pipeline_error"] = None
        st.session_state["last_run_ok"] = False

        banner_slot.markdown(
            '<div class="banner-warn"><strong>⚡ Pipeline Running</strong> — LangGraph streaming via API.</div>',
            unsafe_allow_html=True,
        )
        st.session_state["active_node"] = None
        _render_pipeline_graph(None, container=pipeline_slot)

        _render_telemetry_sidebar(status_telemetry_slot)
        _render_terminal(st.session_state["console_logs"], container=terminal_slot)
        _render_code_editor("", container=code_slot, readonly=True)

        try:
            final_state = _stream_from_api(
                prompt_text,
                st.session_state["thread_id"],
                recursion_limit,
                terminal_slot=terminal_slot,
                code_slot=code_slot,
                telemetry_slot=status_telemetry_slot,
                file_tabs_slot=file_tabs_slot,
                pipeline_slot=pipeline_slot,
            )
            st.session_state["dashboard_state"] = final_state
            st.session_state["last_run_ok"] = True
            st.session_state["pipeline_error"] = None

            verified = bool(final_state.get("is_verified"))
            intent = final_state.get("intent", "—")

            # Update active file in session state
            if final_state.get("active_file"):
                st.session_state["active_file"] = final_state["active_file"]

            banner_slot.markdown(
                f"""
                <div class="banner-ok">
                <strong>✓ Pipeline Complete</strong>
                intent={intent} · verified={'yes' if verified else 'no'}
                <div class="ide-mode-badge" style="display: inline-flex; margin-left: 0.5rem;">
                    <div class="ide-mode-dot"></div> LIVE
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.rerun()
        except Exception as exc:
            st.session_state["pipeline_error"] = str(exc)
            st.session_state["last_run_ok"] = False
            _append_console(f"[System] Pipeline error: {exc}")
            _render_terminal(st.session_state["console_logs"], container=terminal_slot)
            banner_slot.markdown(
                f"""
                <div class="banner-error">
                <strong>✗ Pipeline Failed</strong> — {exc}
                </div>
                """,
                unsafe_allow_html=True,
            )

else:
    # Render historical or standby data
    state = st.session_state.get("dashboard_state")
    if state and isinstance(state, dict):
        tel = state.get("telemetry")
        if tel:
            st.session_state["telemetry"] = tel

    _render_telemetry_sidebar(status_telemetry_slot)

    # Render workspace files
    workspace = (state or {}).get("workspace_files") or {}
    active = st.session_state.get("active_file", "main.py")

    if workspace:
        _render_file_tabs(workspace, active, container=file_tabs_slot)
        code = workspace.get(active, "")
    else:
        code = (state or {}).get("code_buffer", "")

    _render_code_editor(code, container=code_slot, readonly=False)

    logs = st.session_state.get("console_logs", "")
    if logs.strip():
        _render_terminal(logs, container=terminal_slot)
    elif state:
        term = (state.get("terminal_output") or "").strip()
        logs_list = state.get("pipeline_logs") or []
        combined = "\n".join(logs_list + ([term] if term else []))
        _render_terminal(combined if combined else "Awaiting pipeline execution…", container=terminal_slot)
    else:
        _render_terminal("Awaiting pipeline execution…", container=terminal_slot)

if st.session_state.get("pipeline_error"):
    st.markdown(
        f'<div class="banner-error"><strong>Last error:</strong> {st.session_state["pipeline_error"]}</div>',
        unsafe_allow_html=True,
    )