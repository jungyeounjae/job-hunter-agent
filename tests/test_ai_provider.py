from unittest.mock import patch

from pydantic import BaseModel

from ai_provider import embed_texts, generate_korean_text, generate_structured


@patch("ai_provider.openai_client.embed_texts", return_value=[[1.0, 0.0]])
def test_embed_routes_to_openai(mock_oai):
    assert embed_texts(["hello"]) == [[1.0, 0.0]]
    mock_oai.assert_called_once()


@patch("ai_provider.openai_client.generate_korean_text", return_value="한국어 이유")
def test_generate_korean_text_routes_to_openai(mock_oai):
    assert generate_korean_text("prompt") == "한국어 이유"
    mock_oai.assert_called_once()


class _SampleModel(BaseModel):
    name: str
    score: float


@patch("ai_provider.openai_client.generate_structured")
def test_generate_structured_routes_to_openai(mock_gen):
    mock_gen.return_value = _SampleModel(name="test", score=1.0)
    result = generate_structured("prompt", _SampleModel)
    assert result.name == "test"
    mock_gen.assert_called_once_with("prompt", _SampleModel)
