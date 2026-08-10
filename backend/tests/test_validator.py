from src.agents.validator import validator_node

def test_validator_empty_code():
    state = {"code_buffer": "", "active_file": "main.py", "validator_attempts": 0}
    result = validator_node(state)
    assert result["validation_passed"] is False
    assert any("Empty code buffer" in msg for msg in result["validator_feedback"])

def test_validator_banned_imports():
    state = {
        "code_buffer": "import os\nos.remove('file')",
        "active_file": "main.py",
        "validator_attempts": 0
    }
    result = validator_node(state)
    assert result["validation_passed"] is False
    assert any("os.remove" in msg for msg in result["validator_feedback"])

def test_validator_pass():
    state = {
        "code_buffer": "print('hello world')",
        "active_file": "main.py",
        "validator_attempts": 0
    }
    result = validator_node(state)
    assert result["validation_passed"] is True
    assert len(result["validator_feedback"]) == 0
