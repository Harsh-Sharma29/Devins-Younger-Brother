from src.agents.router import router_node

def test_router_coding_intent():
    state = {"user_prompt": "Write a python script to fetch a URL"}
    result = router_node(state)
    assert result["intent"] == "coding"

def test_router_research_intent():
    state = {"user_prompt": "What is the capital of France?"}
    result = router_node(state)
    assert result["intent"] in ["research", "generic"]
