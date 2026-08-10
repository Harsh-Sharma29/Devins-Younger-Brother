"""
Live web search via Tavily for up-to-date API documentation and references.
"""

from __future__ import annotations

import os
from typing import List, Optional

from langchain_core.tools import BaseTool

try:
    from langchain_community.tools.tavily_search import TavilySearchResults
except ImportError:  # pragma: no cover
    TavilySearchResults = None  # type: ignore[misc, assignment]


def get_tavily_tool() -> Optional[BaseTool]:
    """
    Return a configured Tavily search tool, or None if TAVILY_API_KEY is unset.
    """
    if TavilySearchResults is None:
        return None

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return None

    return TavilySearchResults(
        max_results=3,
        include_answer=True,
        include_raw_content=False,
        api_key=api_key,
        name="tavily_search",
        description=(
            "Search the live web for current API documentation, library usage, "
            "release notes, and technical references. "
            "USE THIS TOOL ONLY WHEN: "
            "1. The user asks a general knowledge question. "
            "2. You need the latest documentation for a specific, unknown library. "
            "STRICTLY DO NOT USE THIS TOOL WHEN: "
            "1. You are tasked with writing, fixing, or generating Python code. "
            "2. You need to read a file from a GitHub repository (use the GitHub tools instead)."
        ),
    )


def get_tavily_tools() -> List[BaseTool]:
    """Return a list suitable for ToolNode / bind_tools (empty if unavailable)."""
    tool = get_tavily_tool()
    return [tool] if tool is not None else []


def tavily_configured() -> bool:
    return get_tavily_tool() is not None
