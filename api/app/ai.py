"""Thin OpenAI client over httpx. Keys stay on the server; the browser only calls our API.

Every function returns None on any failure (no key, timeout, refusal, bad JSON) so callers fall back
to the manual path without an error screen. Model names come from environment variables.
"""
import json
import os
from typing import Any, Optional

import httpx

TIMEOUT_S = 8.0


def _base() -> str:
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def intake_model() -> str:
    return os.environ.get("MODEL_INTAKE", "")


def transcribe_model() -> str:
    return os.environ.get("MODEL_TRANSCRIBE", "")


def ai_enabled() -> bool:
    return bool(_key() and intake_model())


def structured_call(system: str, user: str, name: str, schema: dict, model: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Responses API with a strict json_schema. Returns the parsed object, or None."""
    model = model or intake_model()
    if not (_key() and model):
        return None
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
    }
    try:
        r = httpx.post(f"{_base()}/responses", json=body, timeout=TIMEOUT_S,
                       headers={"Authorization": f"Bearer {_key()}"})
        r.raise_for_status()
        return parse_structured(r.json())
    except Exception:
        return None


def parse_structured(payload: dict) -> Optional[dict[str, Any]]:
    """Pull the JSON object out of a Responses payload. A refusal is checked before anything else."""
    for item in payload.get("output", []) or []:
        for part in item.get("content", []) or []:
            if part.get("type") == "refusal":
                return None
    for item in payload.get("output", []) or []:
        for part in item.get("content", []) or []:
            if part.get("type") == "output_text":
                try:
                    out = json.loads(part.get("text", ""))
                except ValueError:
                    return None
                return out if isinstance(out, dict) else None
    return None


def transcribe(audio: bytes, content_type: str = "audio/webm") -> Optional[str]:
    model = transcribe_model()
    if not (_key() and model and audio):
        return None
    ext = "mp4" if "mp4" in content_type else "ogg" if "ogg" in content_type else "wav" if "wav" in content_type else "webm"
    try:
        r = httpx.post(
            f"{_base()}/audio/transcriptions", timeout=TIMEOUT_S * 2,
            headers={"Authorization": f"Bearer {_key()}"},
            data={"model": model}, files={"file": (f"clip.{ext}", audio, content_type)},
        )
        r.raise_for_status()
        text = r.json().get("text", "")
        return text.strip() or None
    except Exception:
        return None
