"""Ollama local AI — tags, captions, and similarity hints."""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from app_settings import load_app_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llava"
TEXT_MODEL = "llama3.2"


class OllamaProvider:
    def __init__(self, base_url: Optional[str] = None) -> None:
        settings = load_app_settings()
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.enabled = settings.enable_local_ai

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def _generate(self, model: str, prompt: str, images: Optional[list[str]] = None) -> Optional[str]:
        if not self.enabled:
            return None
        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if images:
            payload["images"] = images
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return str(body.get("response", "")).strip() or None
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Ollama generate failed: %s", exc)
            return None

    @staticmethod
    def _image_b64(path: str) -> Optional[str]:
        try:
            with open(path, "rb") as fh:
                return base64.b64encode(fh.read()).decode("ascii")
        except OSError:
            return None

    def generate_tags(self, image_path: str, model: str = DEFAULT_MODEL) -> list[str]:
        b64 = self._image_b64(image_path)
        if not b64:
            return []
        prompt = (
            "List 5-10 descriptive tags for this image as a comma-separated list. "
            "Tags only, no sentences."
        )
        text = self._generate(model, prompt, images=[b64])
        if not text:
            return []
        tags = [t.strip().lower() for t in text.replace("\n", ",").split(",") if t.strip()]
        return tags[:12]

    def generate_caption(self, image_path: str, model: str = DEFAULT_MODEL) -> Optional[str]:
        b64 = self._image_b64(image_path)
        if not b64:
            return None
        prompt = "Write one concise sentence describing this image."
        return self._generate(model, prompt, images=[b64])

    def find_similar(self, image_path: str, candidates: list[str], limit: int = 12) -> list[str]:
        """Basic similarity: compare generated tags against candidate tags in storage."""
        from ocr_index import get_ai_tags

        query_tags = set(self.generate_tags(image_path))
        if not query_tags:
            return candidates[:limit]
        scored: list[tuple[int, str]] = []
        for path in candidates:
            if path == image_path:
                continue
            other_tags = set(get_ai_tags(path))
            if not other_tags:
                continue
            overlap = len(query_tags & other_tags)
            if overlap:
                scored.append((overlap, path))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [p for _, p in scored[:limit]]
