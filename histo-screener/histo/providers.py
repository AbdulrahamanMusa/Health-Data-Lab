"""Model providers: Claude (Anthropic) and Gemini (Google), behind one function.

Each call sends one prepared JPEG plus the shared instructions and gets back
the shared JSON report. API keys come from the visitor (their own key, held in
their session only) or from the server environment (ANTHROPIC_API_KEY,
GEMINI_API_KEY); a visitor's own key always wins. Model IDs can be overridden
in the environment.
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


def server_key(provider: str) -> str | None:
    if provider == "claude":
        return os.environ.get("ANTHROPIC_API_KEY") or None
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def resolve_key(provider: str, user_keys: dict | None = None) -> tuple[str | None, str | None]:
    """(key, source): the visitor's own key first, then the server's."""
    own = (user_keys or {}).get(provider)
    if own:
        return own, "you"
    key = server_key(provider)
    return (key, "server") if key else (None, None)


def available(provider: str, user_keys: dict | None = None) -> bool:
    return resolve_key(provider, user_keys)[0] is not None


def verify_key(provider: str, key: str) -> tuple[bool, str]:
    """A free call that proves a key works (lists one model)."""
    try:
        if provider == "claude":
            import anthropic

            anthropic.Anthropic(api_key=key, max_retries=0, timeout=20).models.list(limit=1)
        else:
            from google import genai

            next(iter(genai.Client(api_key=key).models.list(config={"page_size": 1})), None)
    except Exception as e:  # noqa: BLE001 - any failure means the key cannot be used
        name = type(e).__name__
        if "Authentication" in name or "PermissionDenied" in name or getattr(e, "code", None) in (400, 401, 403):
            return False, "This key was rejected. Check that it was copied completely."
        return False, f"Could not check the key right now ({name}). It may still work."
    return True, "Key works."


class AnalysisError(Exception):
    """A failure the user should see in plain language."""


def _claude(image: bytes, model: str, api_key: str) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
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
        raise AnalysisError("The Anthropic API key was rejected. Check the key under API keys.") from e
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


def _gemini(image: bytes, model: str, api_key: str) -> tuple[dict, dict]:
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=api_key)
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
            raise AnalysisError("The Gemini API key was rejected. Check the key under API keys.") from e
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


def analyse(image: bytes, option: ModelOption, user_keys: dict | None = None) -> dict:
    """Run one model; always returns a dict (with "error" on failure)."""
    started = time.monotonic()
    key, source = resolve_key(option.provider, user_keys)
    if key is None:
        vendor = "Anthropic" if option.provider == "claude" else "Google Gemini"
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"{option.label} needs an API key. Add your {vendor} key under API keys."}
    try:
        report, usage = (_claude if option.provider == "claude" else _gemini)(image, option.id, key)
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
        "key_source": source,
        "seconds": round(time.monotonic() - started, 1),
    }
