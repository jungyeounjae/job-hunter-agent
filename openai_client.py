import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from llm_config import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL
from usage_tracker import record_usage


class OpenAIClientError(RuntimeError):
    pass


T = TypeVar("T", bound=BaseModel)


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIClientError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        model = DEFAULT_EMBEDDING_MODEL
        response = _client().embeddings.create(model=model, input=texts)
        record_usage("embeddings", model, response.usage)
        return [list(item.embedding) for item in response.data]
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc


def generate_korean_text(prompt: str) -> str:
    try:
        model = DEFAULT_CHAT_MODEL
        response = _client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        record_usage("chat", model, response.usage)
        content = response.choices[0].message.content
        if not content:
            raise OpenAIClientError("Empty response from OpenAI")
        return content.strip()
    except OpenAIClientError:
        raise
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc


def generate_structured(prompt: str, model_type: type[T]) -> T:
    try:
        model = DEFAULT_CHAT_MODEL
        response = _client().beta.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=model_type,
        )
        record_usage("structured", model, response.usage)
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise OpenAIClientError("Structured parse returned empty")
        return parsed
    except OpenAIClientError:
        raise
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc
