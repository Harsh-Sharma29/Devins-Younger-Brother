import pytest
from src.core.graph import get_initial_state

@pytest.fixture
def initial_state():
    return get_initial_state("Test prompt")
