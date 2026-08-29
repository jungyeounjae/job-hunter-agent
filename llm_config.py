"""OpenAI model IDs — cost-optimized defaults (override via .env)."""

import os

# Cheapest OpenAI chat + embedding tiers (see .env.example)
DEFAULT_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano")
DEFAULT_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def crew_llm_model_id() -> str:
    """LiteLLM / CrewAI format: openai/<model>."""
    model = DEFAULT_CHAT_MODEL
    if not model.startswith("openai/"):
        return f"openai/{model}"
    return model
