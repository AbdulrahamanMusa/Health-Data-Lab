"""Model providers: Claude (Anthropic) and Gemini (Google), behind one function.

Each call sends one prepared JPEG plus the shared instructions and gets back
the shared JSON report. API keys come from the environment only
(ANTHROPIC_API_KEY, GEMINI_API_KEY); model IDs can be overridden there too.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass

from .prompt import SCHEMA, SYSTEM, USER, normalise


@dataclass(frozen=True)
class ModelOption:
    id: str  # the provider's model ID
    provider: str  # "claude" or "gemini"
    label: str
    note: str


def model_options() -> list[ModelOption]:
    return [
        ModelOption(os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"), "claude", "Claude Opus 5.5", "Most thorough reasoning"),
        ModelOption(os.environ.get("CLAUDE_FAST_MODEL", "claude-sonnet-5-5"), "claude", "Claude Sonnet 5.5", "Faster, lower cost"),
        ModelOption(os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"), "gemini", "Gemini 3.8 Flash", "Fast multimodal"),
        ModelOption(os.environ.get("GEMINI_PRO_MODEL", "gemini-3.1-pro-preview"), "gemini", "Gemini 3.1 Pro (preview)", "Deeper analysis"),
    ]


def available(provider: str) -> bool:
    if provider == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


class AnalysisError(Exception):
    """A failure the user should see in plain language."""


def _claude(image: bytes, model: str) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic()
    try:
        # Server-side fallback: if a safety classifier declines, the API retries
        # on Anthropic's recommended model for that category within the same call.
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(image).decode()}},
                        {"type": "text", "text": USER},
                    ],
                }
            ],
        )
    except anthropic.AuthenticationError as e:
        raise AnalysisError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.") from e
    except anthropic.RateLimitError as e:
        raise AnalysisError("Claude is rate-limited right now. Try again in a minute.") from e
    except anthropic.BadRequestError as e:
        raise AnalysisError(f"Claude could not process this request: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise AnalysisError(f"Claude returned an error ({e.status_code}). Try again shortly.") from e
    except anthropic.APIConnectionError as e:
        raise AnalysisError("Could not reach the Claude API. Check the server's internet connection.") from e

    if response.stop_reason == "refusal":
        raise AnalysisError("Claude declined to analyse this image.")
    if response.stop_reason == "max_tokens":
        raise AnalysisError("Claude's report was cut off. Try again.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "served_by": response.model}
    return json.loads(text), usage


def _gemini(image: bytes, model: str) -> tuple[dict, dict]:
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    try:
        response = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=image, mime_type="image/jpeg"), USER],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
            ),
        )
    except errors.ClientError as e:
        if getattr(e, "code", None) in (401, 403):
            raise AnalysisError("The Gemini API key was rejected. Check GEMINI_API_KEY.") from e
        if getattr(e, "code", None) == 429:
            raise AnalysisError("Gemini is rate-limited right now. Try again in a minute.") from e
        raise AnalysisError(f"Gemini could not process this request: {e}") from e
    except errors.ServerError as e:
        raise AnalysisError("Gemini returned a server error. Try again shortly.") from e
    if not response.text:
        raise AnalysisError("Gemini returned no report (the image may have been blocked).")
    meta = response.usage_metadata
    usage = {
        "input_tokens": getattr(meta, "prompt_token_count", None),
        "output_tokens": getattr(meta, "candidates_token_count", None),
        "served_by": model,
    }
    return json.loads(response.text), usage


def analyse(image: bytes, option: ModelOption) -> dict:
    """Run one model; always returns a dict (with "error" on failure)."""
    started = time.monotonic()
    if not available(option.provider):
        key = "ANTHROPIC_API_KEY" if option.provider == "claude" else "GEMINI_API_KEY"
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"{option.label} is not configured on this server (missing {key})."}
    try:
        report, usage = (_claude if option.provider == "claude" else _gemini)(image, option.id)
        report = normalise(report)
    except AnalysisError as e:
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": str(e)}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"The model's report could not be read ({type(e).__name__})."}
    except Exception as e:  # noqa: BLE001 - network or SDK failures: report, never crash the session
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"{option.label} could not be reached ({type(e).__name__}). Try again shortly."}
    return {
        "model": option.id,
        "label": option.label,
        "provider": option.provider,
        "report": report,
        "usage": usage,
        "seconds": round(time.monotonic() - started, 1),
    }
