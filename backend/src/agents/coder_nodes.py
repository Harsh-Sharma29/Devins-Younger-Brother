"""
Coder agent nodes — LLM (Configured LLM) + ToolNode ReAct loop + code extraction.

Graph flow:
  coder_model → (tool calls?) → coder_tools → coder_model → coder_finalize
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from src.core.llm_factory import get_llm
from langgraph.prebuilt import ToolNode

from src.agents.coder import (
    _determine_entry_file,
    _parse_multi_file_output,
)
from src.core.llm_fallback import sanitize_code_for_buffer
from src.core.memory import format_history_context, get_state_field, record_assistant_turn
from src.tools.file_ops import write_code_to_disk, write_workspace_to_disk
from src.tools.web_search import get_tavily_tools, tavily_configured
from src.tools.github_tools import get_github_tools

MAX_CODER_TOOL_ROUNDS = 3

CODER_SYSTEM_PROMPT = (
    "You are an expert Python developer.\n"
    "Return ONLY valid Python code in your final answer.\n"
    "When the task requires multiple files, output them using this separator format:\n"
    "# --- FILE: filename.py ---\n"
    "<code for that file>\n"
    "# --- FILE: another_file.py ---\n"
    "<code for another file>\n\n"
    "If only one file is needed, wrap it in a single markdown code fence.\n"
    "The entry point file should be named main.py unless the user specifies otherwise.\n"
    "Code must run in an isolated Docker sandbox. Always wrap network and file I/O in try/except blocks.\n"
    "Never embed API keys or secrets. Never use os.remove, shutil.rmtree, eval, exec, or shell=True subprocess calls.\n"
    "For HTTP calls, use Python's built-in urllib.request — do NOT import 'requests' (not available).\n\n"
    "CRITICAL INSTRUCTION: Whenever you write code involving network requests, API calls, or I/O operations, you MUST wrap the actual execution in a comprehensive try...except block to gracefully handle connection and decoding errors.\n\n"
    "TOOL ROUTING PROTOCOL (Strictly Follow TWO-PHASE EXECUTION):\n"
    "Phase 1 (Tool Invocation): If the task involves fetching files or reading READMEs from a repository, you MUST always execute your GitHub tools FIRST to retrieve the raw string content into your context.\n"
    "Phase 2 (Code Generation): CRITICAL: If a GitHub tool has already fetched text into the message history, extract that EXACT string from the tool output and place it directly into a variable inside main.py using triple-quotes ('''...''').\n"
    "NEVER write python code that uses `urllib`, `requests`, `http.client`, or any networking module to download content at runtime. The file must be 100% offline and self-contained.\n\n"
    "You must analyze the user's intent before invoking any tool.\n"
    "- Intent = External Knowledge: Use Tavily search ONLY for looking up unknown API documentations or general knowledge.\n"
    "- Intent = Code Generation: Once you have fetched the necessary context, DO NOT use Tavily Search to figure out how to write the code. Rely on your internal knowledge to immediately write the final Python script.\n"
    "After using a tool and receiving its output, you MUST immediately produce your final code output. Do NOT chain additional tool calls unless absolutely necessary for a different intent."
)

_tavily_tools = get_tavily_tools() # Retained for import if needed elsewhere, but not bound to Coder
_github_tools = get_github_tools()
_coder_tools = None  # Disabled to prevent proxy connection errors and infinite ReAct loops

_coder_tool_node = (
    ToolNode(_coder_tools, messages_key="coder_messages") if _coder_tools else None
)


def _messages_from_state(state: Any) -> List[BaseMessage]:
    raw = get_state_field(state, "coder_messages", []) or []
    return list(raw)


from src.core.memory_rag import retrieve_context

def _build_user_message(state: Any) -> str:
    user_prompt = get_state_field(state, "user_prompt", "") or ""
    history = get_state_field(state, "conversation_history", []) or []
    validator_feedback = get_state_field(state, "validator_feedback", []) or []
    context = format_history_context(history)

    # Retrieve RAG context globally
    rag_context = retrieve_context(user_prompt, thread_id="global_workspace", k=5)
    if rag_context:
        rag_context = f"\n\n{rag_context}\n"

    message = (
        f"Conversation context (last exchanges):\n{context}\n"
        f"{rag_context}"
        f"\nTask:\n{user_prompt}"
    )
    if validator_feedback:
        feedback_block = "\n".join(f"- {item}" for item in validator_feedback)
        message += (
            f"\n\n[Validator — rewrite required before sandbox]:\n{feedback_block}\n"
            "Fix every issue above. Return the full corrected Python file(s) only."
        )
    return message


def _llm_with_tools():
    llm = get_llm(temperature=0)
    if _coder_tools:
        return llm.bind_tools(_coder_tools)
    return llm


def coder_model_node(state: Any) -> Dict[str, Any]:
    """Invoke Groq LLM (tool-capable). Appends AIMessage; routes to ToolNode if needed."""
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    used_hf_failover = bool(get_state_field(state, "used_hf_failover", False))
    terminal_output = get_state_field(state, "terminal_output", "") or ""
    history = list(get_state_field(state, "conversation_history", []) or [])
    validator_feedback = get_state_field(state, "validator_feedback", []) or []
    tool_rounds = int(get_state_field(state, "coder_tool_rounds", 0) or 0)

    # Fresh message chain on validator rewrite or first coder pass
    prior_messages = _messages_from_state(state)
    if validator_feedback or not prior_messages:
        user_message = _build_user_message(state)
        messages: List[BaseMessage] = [
            SystemMessage(content=CODER_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        if validator_feedback:
            pipeline_logs.append("[Coder] Incorporating Validator self-reflection feedback…")
        tool_rounds = 0
    else:
        messages = prior_messages

    search_note = " (Tavily web search enabled)" if tavily_configured() else ""
    pipeline_logs.append(f"[Coder] Invoking LLM (primary: Configured LLM){search_note}…")

    try:
        llm = _llm_with_tools()
        response = llm.invoke(messages)
    except Exception as exc:
        pipeline_logs.append(f"[Coder] LLM tool syntax error ({exc}). Retrying...")
        messages.append(HumanMessage(content=f"System Error: Your previous response caused an exception: {exc}\nYou likely output raw text instead of a valid JSON tool call. Please try again, and ensure you use valid tool invocation syntax, or output the final python code directly if no tools are needed."))
        try:
            response = llm.invoke(messages)
        except Exception as exc2:
            error_str = str(exc2)
            pipeline_logs.append(f"[Coder] LLM failure on retry: {exc2}")
            return {
                "coder_messages": [],
                "detected_errors": [error_str],
                "pipeline_logs": pipeline_logs,
                "llm_provider": get_state_field(state, "llm_provider", "groq"),
                "used_hf_failover": used_hf_failover,
                "terminal_output": terminal_output + f"\n[Coder] Error: {exc2}",
                "validation_passed": False,
            }

    if not isinstance(response, AIMessage):
        response = AIMessage(content=str(getattr(response, "content", response)))

    messages = messages + [response]

    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        pipeline_logs.append("[Coder] Invoking Tools...")

    return {
        "coder_messages": messages,
        "coder_tool_rounds": tool_rounds,
        "pipeline_logs": pipeline_logs,
        "llm_provider": "groq",
        "used_hf_failover": used_hf_failover,
        "terminal_output": terminal_output,
        "conversation_history": history,
        "validation_passed": False,
        "validator_feedback": [],
    }


def coder_tool_executor(state: Any) -> Dict[str, Any]:
    """Execute ToolNode and return tool results to the message thread."""
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    tool_rounds = int(get_state_field(state, "coder_tool_rounds", 0) or 0)

    if _coder_tool_node is None:
        pipeline_logs.append("[Coder] Tools unavailable — skipping tools.")
        return {"pipeline_logs": pipeline_logs, "coder_tool_rounds": tool_rounds + 1}

    messages = _messages_from_state(state)
    
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    
    for call in tool_calls:
        tool_name = call.get("name", "")
        if "tavily" in tool_name.lower():
            if not pipeline_logs or pipeline_logs[-1] != "[Coder] Invoking Web Search via Tavily…":
                pipeline_logs.append("[Coder] Invoking Web Search via Tavily…")
        elif "github" in tool_name.lower():
            args = call.get("args", {})
            repo = args.get("repo_name", "unknown")
            pipeline_logs.append(f"[Coder] GitHub Tool: fetching from {repo}...")
        else:
            pipeline_logs.append(f"[Coder] Invoking tool: {tool_name}...")

    try:
        result = _coder_tool_node.invoke({"coder_messages": messages})
        updated_messages = result.get("coder_messages", messages)
        pipeline_logs.append("[Coder] Tool execution complete. Analyzing results…")
        return {
            "coder_messages": updated_messages,
            "coder_tool_rounds": tool_rounds + 1,
            "pipeline_logs": pipeline_logs,
        }
    except Exception as exc:
        pipeline_logs.append(f"[Coder] Tool execution failed: {exc}")
        return {
            "coder_tool_rounds": tool_rounds + 1,
            "pipeline_logs": pipeline_logs,
        }


def route_coder_tools(state: Any) -> Literal["coder_tools", "coder_finalize"]:
    """Route to ToolNode when the last AIMessage contains tool calls."""
    tool_rounds = int(get_state_field(state, "coder_tool_rounds", 0) or 0)
    if tool_rounds >= MAX_CODER_TOOL_ROUNDS:
        return "coder_finalize"

    messages = _messages_from_state(state)
    if not messages:
        return "coder_finalize"

    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    if tool_calls and _coder_tool_node is not None:
        return "coder_tools"
    return "coder_finalize"


def coder_finalize_node(state: Any) -> Dict[str, Any]:
    """Parse the final LLM response into workspace_files / code_buffer."""
    pipeline_logs = list(get_state_field(state, "pipeline_logs", []) or [])
    used_hf_failover = bool(get_state_field(state, "used_hf_failover", False))
    terminal_output = get_state_field(state, "terminal_output", "") or ""
    history = list(get_state_field(state, "conversation_history", []) or [])

    messages = _messages_from_state(state)
    raw_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            raw_content = str(msg.content or "")
            if raw_content.strip():
                break

    if not raw_content.strip():
        pipeline_logs.append("[Coder] No code content in LLM response.")
        return {
            "code_buffer": "",
            "detected_errors": ["Coder returned empty content."],
            "pipeline_logs": pipeline_logs,
            "coder_messages": [],
            "validation_passed": False,
        }

    workspace_files = _parse_multi_file_output(raw_content)

    if workspace_files:
        entry_file = _determine_entry_file(workspace_files)
        filenames = list(workspace_files.keys())
        pipeline_logs.append(
            f"[Coder] Multi-file workspace: {', '.join(filenames)} (entry: {entry_file})"
        )
        write_workspace_to_disk(workspace_files)
        code = workspace_files.get(entry_file, "")
        history = record_assistant_turn(
            history, f"Generated {len(filenames)} files: {', '.join(filenames)}"
        )
        return {
            "code_buffer": code,
            "workspace_files": workspace_files,
            "active_file": entry_file,
            "detected_errors": [],
            "pipeline_logs": pipeline_logs,
            "conversation_history": history,
            "coder_messages": [],
            "llm_provider": "groq",
            "used_hf_failover": used_hf_failover,
            "terminal_output": terminal_output + "\n[Coder] Generated multi-file workspace via Groq.",
            "validation_passed": False,
            "validator_feedback": [],
        }

    code, err = sanitize_code_for_buffer(raw_content)
    if err or not code:
        pipeline_logs.append(f"[Coder] Invalid payload rejected: {err}")
        return {
            "code_buffer": "",
            "detected_errors": [err or "Coder returned non-Python payload."],
            "pipeline_logs": pipeline_logs,
            "coder_messages": [],
            "validation_passed": False,
        }

    filename = "main.py"
    write_code_to_disk(filename, code)
    workspace = {filename: code}
    pipeline_logs.append(f"[Coder] Wrote sanitized code → {filename}")
    history = record_assistant_turn(history, f"Generated {filename} ({len(code)} chars)")

    return {
        "code_buffer": code,
        "workspace_files": workspace,
        "active_file": filename,
        "detected_errors": [],
        "pipeline_logs": pipeline_logs,
        "conversation_history": history,
        "coder_messages": [],
        "llm_provider": "groq",
        "used_hf_failover": used_hf_failover,
        "terminal_output": terminal_output + "\n[Coder] Generated via Groq.",
        "validation_passed": False,
        "validator_feedback": [],
    }
