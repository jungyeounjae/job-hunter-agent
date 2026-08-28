import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel


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
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        response = _client().embeddings.create(model=model, input=texts)
        return [list(item.embedding) for item in response.data]
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc


def generate_korean_text(prompt: str) -> str:
    try:
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        response = _client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
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
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        response = _client().beta.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=model_type,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise OpenAIClientError("Structured parse returned empty")
        return parsed
    except OpenAIClientError:
        raise
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc
