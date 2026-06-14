"""
Local AI integration via OllamaProvider.
"""
from __future__ import annotations

from typing import Optional

from services.ollama_provider import OllamaProvider

_provider: Optional[OllamaProvider] = None


def _get_provider() -> OllamaProvider:
    global _provider
    if _provider is None:
        _provider = OllamaProvider()
    return _provider


def ollama_available() -> bool:
    return _get_provider().available()


def describe_image_local(image_path: str, model: str = "llava") -> Optional[str]:
    return _get_provider().generate_caption(image_path, model=model)


def generate_tags_local(image_path: str) -> list[str]:
    return _get_provider().generate_tags(image_path)


def find_similar_local(image_path: str, candidates: list[str], limit: int = 12) -> list[str]:
    return _get_provider().find_similar(image_path, candidates, limit=limit)
