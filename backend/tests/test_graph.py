import pytest
from src.core.graph import compile_workflow

def test_graph_compiles():
    app = compile_workflow()
    assert app is not None
