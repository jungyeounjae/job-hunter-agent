import dotenv
import pytest

dotenv.load_dotenv()


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch, request):
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
