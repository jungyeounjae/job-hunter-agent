import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
