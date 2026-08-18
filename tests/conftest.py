import pytest
from unittest.mock import patch

@pytest.fixture
def mock_embedding():
    """Mock get_embedding to return deterministic values based on text."""
    def _mock_get_embedding(text):
        # Return a simple vector based on word presence
        vec = [0.0] * 10
        if "wheat" in text.lower():
            vec[0] = 1.0
        if "rice" in text.lower():
            vec[1] = 1.0
        if "sowing" in text.lower():
            vec[2] = 1.0
        if "irrigation" in text.lower():
            vec[3] = 1.0
        return vec
    
    with patch("app.vector_index.get_embedding", side_effect=_mock_get_embedding):
        yield
