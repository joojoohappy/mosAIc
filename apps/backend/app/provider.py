"""Image provider: Google Gemini image models via the Interactions REST API.

Written from https://ai.google.dev/gemini-api/docs/image-generation (checked
2026-10-22). Plain urllib on purpose: one POST does not need an SDK, and every
dependency is one more thing to break on a demo laptop.

Configure in apps/backend/.env (see .env.example):
    GEMINI_API_KEY           required for live generation
    MOSAIC_IMAGE_MODEL       optional, defaults to DEFAULT_MODEL
    MOSAIC_PROVIDER_TIMEOUT  optional seconds, defaults to 60

Contract with generation.py: return image bytes or raise. Never touch the
filesystem, never retry. The caller validates the bytes and decides the mode.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request

NAME = "Google Gemini"
DEFAULT_MODEL = "gemini-nano-banana-2.1"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"

MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def model() -> str:
    return os.environ.get("MOSAIC_IMAGE_MODEL") or DEFAULT_MODEL


def timeout() -> float:
    try:
        return min(float(os.environ.get("MOSAIC_PROVIDER_TIMEOUT", 60)), 60.0)
    except ValueError:
        return 60.0


def build_request(prompt: str, image: bytes, image_kind: str,
                  aspect_ratio: str | None) -> dict:
    response_format: dict = {"type": "image", "mime_type": "image/png"}
    if aspect_ratio:
        response_format["aspect_ratio"] = aspect_ratio
    return {
        "model": model(),
        "input": [
            {"type": "text", "text": prompt},
            {"type": "image", "mime_type": MIME[image_kind],
             "data": base64.b64encode(image).decode("ascii")},
        ],
        "response_format": response_format,
    }


def extract_image(payload: dict) -> bytes:
    """Pull the first image out of an interaction. Raises if there is none --
    a text-only answer (e.g. a safety refusal) is a failure, not a result."""
    data = (payload.get("output_image") or {}).get("data")
    if not data:
        for step in payload.get("steps") or []:
            for block in step.get("content") or []:
                if block.get("type") == "image" and block.get("data"):
                    data = block["data"]
                    break
            if data:
                break
    if not data:
        raise ValueError("provider response contained no image")
    return base64.b64decode(data)


def generate(api_key: str, prompt: str, image: bytes, image_kind: str,
             aspect_ratio: str | None) -> bytes:
    body = json.dumps(build_request(prompt, image, image_kind, aspect_ratio))
    req = urllib.request.Request(
        ENDPOINT,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout()) as resp:  # noqa: S310 - fixed https URL
        return extract_image(json.loads(resp.read()))
