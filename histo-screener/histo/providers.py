"""Model providers: Claude (Anthropic), Gemini (Google) and MedGemma (local), behind one function.

Each call sends one prepared JPEG plus the shared instructions and gets back
the shared JSON report. API keys come from the visitor (their own key, held in
their session only) or from the server environment (ANTHROPIC_API_KEY,
GEMINI_API_KEY); a visitor's own key always wins. Model IDs can be overridden
in the environment.

MedGemma is Google's open medical model. It runs on the host machine through
Ollama (OLLAMA_HOST, default http://127.0.0.1:11434), so it needs no API key
and has no per-call cost; it is offered only when Ollama has the model.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass

from .prompt import SCHEMA, SYSTEM, USER, normalise

log = logging.getLogger("histo")


@dataclass(frozen=True)
class ModelOption:
    id: str  # the provider's model ID
    provider: str  # "claude", "gemini" or "medgemma"
    label: str
    note: str


def model_options() -> list[ModelOption]:
    return [
        ModelOption(os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"), "claude", "Claude Opus 5.5", "Most thorough reasoning"),
        ModelOption(os.environ.get("CLAUDE_FAST_MODEL", "claude-sonnet-5-5"), "claude", "Claude Sonnet 5.5", "Faster, lower cost"),
        ModelOption(os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"), "gemini", "Gemini 3.8 Flash", "Fast multimodal"),
        ModelOption(os.environ.get("GEMINI_PRO_MODEL", "gemini-3.1-pro-preview"), "gemini", "Gemini 3.1 Pro (preview)", "Deeper analysis"),
        ModelOption(medgemma_model(), "medgemma", "MedGemma 4B (local)", "Open model on this computer · free"),
    ]


# ----------------------------------------------------------------- local model (Ollama)

def medgemma_model() -> str:
    return os.environ.get("MEDGEMMA_MODEL", "medgemma:4b")


def ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


_local_cache: dict = {"at": 0.0, "status": None}


def local_status(max_age: float = 10.0) -> dict:
    """Is the local model ready? Cached briefly: this runs on every page refresh."""
    if _local_cache["status"] is not None and time.monotonic() - _local_cache["at"] < max_age:
        return _local_cache["status"]
    import httpx

    model = medgemma_model()
    try:
        tags = httpx.get(f"{ollama_host()}/api/tags", timeout=2).json()
        names = {m.get("name") for m in tags.get("models", [])} | {m.get("model") for m in tags.get("models", [])}
        wanted = {model, model if ":" in model else f"{model}:latest"}
        if names & wanted:
            status = {"ready": True, "model": model, "reason": None}
        else:
            status = {"ready": False, "model": model, "reason": "not_downloaded"}
    except Exception:  # noqa: BLE001 - Ollama not installed, not running or unreachable
        status = {"ready": False, "model": model, "reason": "not_running"}
    _local_cache.update(at=time.monotonic(), status=status)
    return status


def server_key(provider: str) -> str | None:
    if provider == "claude":
        return os.environ.get("ANTHROPIC_API_KEY") or None
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def resolve_key(provider: str, user_keys: dict | None = None) -> tuple[str | None, str | None]:
    """(key, source): the visitor's own key first, then the server's. The local model needs none."""
    if provider == "medgemma":
        return ("local", "local") if local_status()["ready"] else (None, None)
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

    # Busy (429) and server (5xx) errors are usually transient: retry with backoff.
    retry = types.HttpRetryOptions(attempts=4, initial_delay=2, max_delay=20, http_status_codes=[429, 500, 502, 503, 504])
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=180_000))
    try:
        response = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=image, mime_type="image/jpeg"), USER],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except errors.APIError as e:
        # Status and Google's message only; neither contains the key.
        log.warning("Gemini %s failed: %s %s %s", model, e.code, e.status, (e.message or "")[:300])
        _gemini_error(e)
    if not response.text:
        raise AnalysisError("Gemini returned no report (the image may have been blocked).")
    meta = response.usage_metadata
    usage = {
        "input_tokens": getattr(meta, "prompt_token_count", None),
        "output_tokens": getattr(meta, "candidates_token_count", None),
        "served_by": model,
    }
    return json.loads(response.text), usage


def _gemini_error(e) -> None:
    from google.genai import errors

    detail = f"{e.code} {e.status or ''}: {(e.message or '').strip()[:200]}".strip()
    if isinstance(e, errors.ClientError):
        if e.code in (401, 403):
            raise AnalysisError("The Gemini API key was rejected. Check the key under API keys.") from e
        if e.code == 429:
            raise AnalysisError(f"Gemini rate limit or quota reached for this key. Wait a minute, or try the other Gemini model. ({detail})") from e
        if e.code == 404:
            raise AnalysisError(f"This Gemini model isn't available to your key. Try the other Gemini model. ({detail})") from e
        raise AnalysisError(f"Gemini could not process this request. ({detail})") from e
    raise AnalysisError(f"Gemini's servers are busy or failed after several retries. Try again shortly, or switch model. ({detail})") from e


def _medgemma(image: bytes, model: str, _key: str) -> tuple[dict, dict]:
    import httpx

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER, "images": [base64.standard_b64encode(image).decode()]},
        ],
        "format": SCHEMA,  # Ollama constrains the output to this JSON schema
        "stream": False,
        "keep_alive": "15m",
        "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 2500},
    }
    try:
        # CPU-only machines can take a few minutes for one report.
        r = httpx.post(f"{ollama_host()}/api/chat", json=body, timeout=httpx.Timeout(900, connect=5))
    except httpx.ConnectError as e:
        raise AnalysisError("The local model isn't reachable. Start Ollama and try again.") from e
    except httpx.TimeoutException as e:
        raise AnalysisError("The local model took too long. A GPU, or a smaller image, makes it faster.") from e
    if r.status_code == 404:
        raise AnalysisError(f"MedGemma isn't downloaded yet. Run: ollama pull {model}")
    if r.status_code >= 400:
        detail = (r.json().get("error") if r.headers.get("content-type", "").startswith("application/json") else r.text) or ""
        log.warning("MedGemma %s failed: %s %s", model, r.status_code, str(detail)[:300])
        raise AnalysisError(f"The local model failed ({r.status_code}: {str(detail)[:200]}).")
    data = r.json()
    if data.get("done_reason") == "length":
        raise AnalysisError("MedGemma's report was cut off. Try again.")
    usage = {"input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"), "served_by": f"{model} (local)"}
    return json.loads(data["message"]["content"]), usage


def analyse(image: bytes, option: ModelOption, user_keys: dict | None = None) -> dict:
    """Run one model; always returns a dict (with "error" on failure)."""
    started = time.monotonic()
    key, source = resolve_key(option.provider, user_keys)
    if key is None and option.provider == "medgemma":
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"{option.label} isn't available. Start Ollama and run: ollama pull {option.id}"}
    if key is None:
        vendor = "Anthropic" if option.provider == "claude" else "Google Gemini"
        return {"model": option.id, "label": option.label, "provider": option.provider, "error": f"{option.label} needs an API key. Add your {vendor} key under API keys."}
    try:
        call = {"claude": _claude, "gemini": _gemini, "medgemma": _medgemma}[option.provider]
        report, usage = call(image, option.id, key)
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
