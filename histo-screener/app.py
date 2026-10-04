"""Histopathology Screener: AI-assisted screening of histology images.

For research and medical education only, not for diagnosis. Claude and Gemini
read the same image with the same instructions and fill the same structured
report, so their answers can be compared side by side. The server holds only
computation; the UI is the React client in src/ (built to www/ui.js). Uploaded
images live in this session's memory only and are never written to disk.
"""

import asyncio
import base64
import copy
import os
from datetime import date, datetime

from shiny import reactive
from shiny.express import input, session
from shinyreact import reactive_output, send_message, set_react_page

from histo import images, providers, report

set_react_page()

MAX_PER_SESSION = int(os.environ.get("MAX_ANALYSES_PER_SESSION", "20"))
MAX_PER_DAY = int(os.environ.get("MAX_ANALYSES_PER_DAY", "200"))
_daily = {"day": date.today(), "count": 0}  # module-level: shared by all sessions in this process

cases = reactive.value({})  # case_id -> case dict (this session only)
current = reactive.value(None)
used = reactive.value(0)
running_models = reactive.value([])
running_case = reactive.value(None)  # the case an in-flight analysis belongs to
# Visitors' own API keys: this session's memory only. Never written to disk or
# logs, and never included in any output sent back to the browser.
user_keys = reactive.value({})
key_checks = reactive.value({})  # provider -> {"ok": bool, "message": str}


def _options():
    return {o.id: o for o in providers.model_options()}


def _public_case(c: dict | None) -> dict | None:
    if c is None:
        return None
    out = {k: c[k] for k in ("id", "name", "source", "width", "height", "data_url", "added", "reference")}
    out["results"] = copy.deepcopy(c["results"])  # annotated below; never mutate stored state
    return out


async def toast(title, text="", level="ok"):
    await send_message(session, "toast", {"title": title, "text": text, "level": level})


def _add_case(prepared: images.Prepared, name: str, source: str, reference: dict | None):
    with reactive.isolate():
        all_cases = dict(cases())
    cid = prepared.digest[:12]
    if cid not in all_cases:
        all_cases[cid] = {
            "id": cid,
            "name": name,
            "source": source,
            "width": prepared.width,
            "height": prepared.height,
            "jpeg": prepared.jpeg,
            "data_url": prepared.data_url(),
            "results": {},
            "added": datetime.now().isoformat(timespec="seconds"),
            "reference": reference,
        }
        cases.set(all_cases)
    current.set(cid)


def _key_status() -> dict:
    """What the browser may know about keys: source and a 4-character hint, never the key."""
    out = {}
    checks = key_checks()
    for provider in ("claude", "gemini"):
        key, source = providers.resolve_key(provider, user_keys())
        out[provider] = {
            "source": source,
            "hint": f"••••{key[-4:]}" if source == "you" and key else None,
            "server": providers.server_key(provider) is not None,
            "check": checks.get(provider),
        }
    return out


# ----------------------------------------------------------------- outputs


@reactive_output
def meta():
    opts = providers.model_options()
    return {
        "models": [{"id": o.id, "provider": o.provider, "label": o.label, "note": o.note, "available": providers.available(o.provider, user_keys())} for o in opts],
        "keys": _key_status(),
        "samples": [{k: s[k] for k in ("id", "thumb", "reference_diagnosis", "reference_label", "site", "author", "license", "license_url", "source_url")} for s in images.samples()],
        "limits": {"per_session": MAX_PER_SESSION, "max_upload_mb": images.MAX_UPLOAD_MB},
    }


@reactive_output
def workspace():
    all_cases = cases()
    cid = current()
    case = _public_case(all_cases.get(cid)) if cid else None
    if case:
        done = [r for r in case["results"].values() if r.get("report")]
        case["agreement"] = report.agreement(done)
        ref = case.get("reference")
        for r in case["results"].values():
            if r.get("report") and ref:
                r["reference_check"] = report.reference_check(r["report"]["classification"]["label"], ref["reference_label"])
    history = [
        {
            "id": c["id"],
            "name": c["name"],
            "source": c["source"],
            "added": c["added"],
            "labels": [r["report"]["classification"]["label"] for r in c["results"].values() if r.get("report")],
        }
        for c in sorted(all_cases.values(), key=lambda c: c["added"], reverse=True)
    ]
    return {
        "case": case,
        "history": history,
        "running": run_analysis.status() == "running",
        "running_models": running_models() if running_case() == cid else [],
        "used": used(),
        "remaining": max(0, MAX_PER_SESSION - used()),
    }


# ------------------------------------------------------------------ events


@reactive.extended_task
async def run_analysis(jpeg: bytes, model_ids: list[str], keys: dict) -> list[dict]:
    opts = _options()
    jobs = [asyncio.to_thread(providers.analyse, jpeg, opts[m], keys) for m in model_ids if m in opts]
    return await asyncio.gather(*jobs)


@reactive.effect
@reactive.event(input.analyse)
async def _analyse():
    d = input.analyse()
    if not d or not d.get("models"):
        return
    with reactive.isolate():
        cid, all_cases, n_used, keys = current(), cases(), used(), dict(user_keys())
    if not cid or cid not in all_cases:
        await toast("Choose an image first", "Pick a sample slide or upload your own.", "warn")
        return
    if run_analysis.status() == "running":
        return
    models = [m for m in d["models"] if m in _options()][:2]
    # Limits protect the server owner's bill; visitors using their own keys pay their own way.
    on_server_key = [m for m in models if providers.resolve_key(_options()[m].provider, keys)[1] != "you"]
    if not on_server_key:
        running_models.set(models)
        running_case.set(cid)
        run_analysis(all_cases[cid]["jpeg"], models, keys)
        return
    if n_used + len(on_server_key) > MAX_PER_SESSION:
        await toast("Session limit reached", f"The shared demo key allows {MAX_PER_SESSION} analyses per visit. Add your own API key to keep going.", "warn")
        return
    today = date.today()
    if _daily["day"] != today:
        _daily.update(day=today, count=0)
    if _daily["count"] + len(on_server_key) > MAX_PER_DAY:
        await toast("Daily limit reached", "The shared demo key has reached today's limit. Add your own API key to keep going.", "warn")
        return
    _daily["count"] += len(on_server_key)
    used.set(n_used + len(on_server_key))
    running_models.set(models)
    running_case.set(cid)
    run_analysis(all_cases[cid]["jpeg"], models, keys)


@reactive.effect
async def _collect():
    if run_analysis.status() not in ("success", "error"):
        return
    with reactive.isolate():
        cid, all_cases = running_case(), dict(cases())
    running_models.set([])
    running_case.set(None)
    if run_analysis.status() == "error":
        await toast("Analysis failed", "Something went wrong while contacting the models. Please try again.", "danger")
        return
    results = run_analysis.result()
    if cid in all_cases:
        case = dict(all_cases[cid])
        case["results"] = {**case["results"], **{r["model"]: r for r in results}}
        all_cases[cid] = case
        cases.set(all_cases)
    errors = [r for r in results if r.get("error")]
    if errors:
        await toast("Some analyses did not complete", errors[0]["error"], "danger")


@reactive.effect
@reactive.event(input.select_sample)
async def _select_sample():
    d = input.select_sample()
    if not d:
        return
    s = next((x for x in images.samples() if x["id"] == d["id"]), None)
    if not s:
        return
    ref = {k: s[k] for k in ("reference_diagnosis", "reference_label", "site", "author", "license", "license_url", "source_url")}
    _add_case(images.sample_image(s["id"]), f"Sample · {s['site']}", "sample", ref)


@reactive.effect
@reactive.event(input.upload)
async def _upload():
    d = input.upload()
    if not d or not d.get("b64"):
        return
    try:
        prepared = images.prepare(base64.b64decode(d["b64"]))
    except images.ImageError as e:
        await toast("Could not use this image", str(e), "danger")
        return
    _add_case(prepared, d.get("name") or "Uploaded image", "upload", None)
    await toast("Image ready", f"{prepared.width}×{prepared.height} px · metadata removed before analysis", "ok")


@reactive.effect
@reactive.event(input.open_case)
async def _open_case():
    d = input.open_case()
    if d and d.get("id") in cases():
        current.set(d["id"])


@reactive.effect
@reactive.event(input.export_report)
async def _export():
    if not input.export_report():
        return
    with reactive.isolate():
        case = cases().get(current())
    if not case or not any(r.get("report") for r in case["results"].values()):
        await toast("Nothing to export yet", "Run an analysis first.", "warn")
        return
    page = report.render(case, list(case["results"].values()))
    await send_message(session, "download", {"filename": f"histology-screening-{case['id']}.html", "text": page, "mime": "text/html"})


def _clean_key(v) -> str:
    v = str(v or "").strip()
    return v if 20 <= len(v) <= 300 and v.isprintable() and " " not in v else ""


@reactive.effect
@reactive.event(input.set_keys)
async def _set_keys():
    d = input.set_keys()
    if not d:
        return
    keys = {p: _clean_key(d.get(p)) for p in ("claude", "gemini")}
    rejected = [p for p in ("claude", "gemini") if d.get(p) and not keys[p]]
    user_keys.set({p: k for p, k in keys.items() if k})
    with reactive.isolate():
        checks = dict(key_checks())
    key_checks.set({p: c for p, c in checks.items() if keys.get(p)})
    if rejected:
        await toast("Key not accepted", "That doesn't look like an API key. Paste the whole key without spaces.", "danger")
    elif d.get("silent"):
        return
    elif any(keys.values()):
        await toast("API keys saved for this session", "Your requests are billed to your own account.", "ok")
    else:
        await toast("API keys cleared", "", "info")


@reactive.effect
@reactive.event(input.test_key)
async def _test_key():
    d = input.test_key()
    if not d or d.get("provider") not in ("claude", "gemini"):
        return
    with reactive.isolate():
        key, source = providers.resolve_key(d["provider"], user_keys())
    if source != "you":
        await toast("Save the key first", "Add your key and press Save, then test it.", "warn")
        return
    ok, message = await asyncio.to_thread(providers.verify_key, d["provider"], key)
    with reactive.isolate():
        checks = dict(key_checks())
    checks[d["provider"]] = {"ok": ok, "message": message}
    key_checks.set(checks)
