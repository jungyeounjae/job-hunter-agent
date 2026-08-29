import os
from unittest.mock import patch

from llm_config import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL, crew_llm_model_id


def test_default_chat_model_is_cost_optimized():
    assert DEFAULT_CHAT_MODEL == "gpt-5-nano"


def test_default_embedding_model_is_small():
    assert DEFAULT_EMBEDDING_MODEL == "text-embedding-3-small"


def test_crew_llm_model_id_prefix():
    with patch.dict(os.environ, {"OPENAI_CHAT_MODEL": "gpt-5-nano"}):
        from importlib import reload
        import llm_config

        reload(llm_config)
        assert llm_config.crew_llm_model_id() == "openai/gpt-5-nano"
