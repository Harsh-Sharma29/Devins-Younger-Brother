from src.agents.coder import _parse_multi_file_output

def test_parse_multi_file_output():
    raw_output = """
# --- FILE: main.py ---
print("hello")
# --- FILE: utils.py ---
def foo(): pass
"""
    files = _parse_multi_file_output(raw_output)
    assert "main.py" in files
    assert "utils.py" in files
    assert "print(\"hello\")" in files["main.py"]

def test_parse_single_file_fallback():
    raw_output = """
```python
print("fallback")
```
"""
    files = _parse_multi_file_output(raw_output)
    assert len(files) == 0  # It returns empty dictionary if no file separators are found
