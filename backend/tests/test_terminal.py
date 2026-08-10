from src.agents.terminal import terminal_agent

def test_terminal_agent_mocked(mocker):
    state = {"workspace_files": {"main.py": "print('ok')"}, "active_file": "main.py"}
    mocker.patch("src.agents.terminal.execute_python_code", return_value={"stdout": "ok\n", "stderr": "", "returncode": 0})
    result = terminal_agent(state)
    assert "ok" in result["terminal_output"]
