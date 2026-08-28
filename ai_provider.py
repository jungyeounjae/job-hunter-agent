import openai_client
from pydantic import BaseModel
from typing import TypeVar


class AiProviderError(RuntimeError):
    pass


T = TypeVar("T", bound=BaseModel)


def embed_texts(texts: list[str]) -> list[list[float]]:
    try:
        return openai_client.embed_texts(texts)
    except openai_client.OpenAIClientError as exc:
        raise AiProviderError(str(exc)) from exc


def generate_korean_text(prompt: str) -> str:
    try:
        return openai_client.generate_korean_text(prompt)
    except openai_client.OpenAIClientError as exc:
        raise AiProviderError(str(exc)) from exc


def generate_structured(prompt: str, model_type: type[T]) -> T:
    try:
        return openai_client.generate_structured(prompt, model_type)
    except openai_client.OpenAIClientError as exc:
        raise AiProviderError(str(exc)) from exc
