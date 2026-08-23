from dotenv import load_dotenv
load_dotenv()


import sys
from unittest.mock import MagicMock
# Mock chromadb to prevent import errors
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.utils'] = MagicMock()
sys.modules['chromadb.utils.embedding_functions'] = MagicMock()

import pytest
from unittest.mock import patch
from src.core.graph import compile_workflow, get_initial_state

def run_pipeline(prompt: str, thread_id: str):
    workflow = compile_workflow()
    state = get_initial_state(prompt)
    config = {"configurable": {"thread_id": thread_id}}
    final_state = workflow.invoke(state, config=config)
    return final_state

def test_heuristic_fallback():
    from src.core.graph import compile_workflow, get_initial_state
    prompt = "Build a modern frontend page with index.html, style.css and script.js."
    state = get_initial_state(prompt)
    
    # We just run the planner node
    from src.agents.planner import planner_agent
    
    with patch("src.agents.planner.get_llm") as mock_get_llm:
        mock_get_llm.side_effect = Exception("Simulated LLM failure")
        res = planner_agent(state)
        
    plan = res.get("artifact_plan", {})
    assert plan.get("runtime") == "Browser"
    assert plan.get("entry") == "index.html"
    assert "heuristic" in plan.get("rationale", "").lower()

@patch("src.agents.coder_nodes.retrieve_context", return_value="")
def test_fastapi_request(mock_rag):
    prompt = "Create a FastAPI backend with a SQLite DB. Include basic CRUD endpoints."
    result = run_pipeline(prompt, thread_id="test_fastapi")
    
    plan = result.get("artifact_plan", {})
    assert plan.get("runtime") == "Python"
    assert result.get("is_verified") == True
