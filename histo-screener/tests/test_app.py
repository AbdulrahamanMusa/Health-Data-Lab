import json
import time

import pytest

from histo import providers

pytestmark = pytest.mark.parametrize("local_server", ["../app.py"], indirect=True)


def fake_analyse(jpeg, option, keys=None):
    label = "malignant" if option.provider == "claude" else "benign"
    rep = {
        "image_assessment": {"is_histology": True, "stain": "H&E", "magnification": "low", "quality": "adequate", "quality_notes": ""},
        "tissue": {"site": "Breast", "tissue_type": "Fibroepithelial", "confidence": "high"},
        "classification": {"label": label, "confidence": 80, "summary": "test"},
        "features": [], "differential": [], "teaching_points": [], "next_steps": [], "limitations": [],
    }
    return {"model": option.id, "label": option.label, "provider": option.provider, "report": rep, "usage": {}, "seconds": 0.1}


def out(s, name):
    for _ in range(50):
        o = s.get_output(name)
        if o.status == "ok":
            return o.value
        s.flush()
    raise AssertionError(name)


def wait_results(s, n, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        s.flush()
        ws = out(s, "workspace")
        if ws["case"] and len([r for r in ws["case"]["results"].values() if r.get("report")]) >= n and not ws["running"]:
            return ws
        time.sleep(0.1)
    raise AssertionError("results never arrived")


def test_meta_lists_models_samples_and_availability(local_server, monkeypatch):
    m = out(local_server, "meta")
    assert {x["provider"] for x in m["models"]} == {"claude", "gemini"}
    assert len(m["samples"]) == 7
    assert all(isinstance(x["available"], bool) for x in m["models"])


def test_compare_two_models_on_a_sample(local_server, monkeypatch):
    monkeypatch.setattr(providers, "analyse", fake_analyse)
    local_server.set_inputs(select_sample={"id": "fibroadenoma", "nonce": 1})
    ws = out(local_server, "workspace")
    assert ws["case"]["source"] == "sample" and ws["case"]["reference"]["reference_label"] == "benign"
    models = [m["id"] for m in out(local_server, "meta")["models"]]
    local_server.set_inputs(analyse={"models": [models[0], models[2]], "nonce": 2})
    ws = wait_results(local_server, 2)
    results = list(ws["case"]["results"].values())
    assert ws["case"]["agreement"]["agree"] is False
    checks = {r["provider"]: r["reference_check"]["status"] for r in results}
    assert checks == {"claude": "disagrees", "gemini": "agrees"}
    assert ws["used"] == 2 and ws["history"][0]["labels"]


SECRET = "sk-ant-api03-VISITOR-SECRET-abcdefghijklmnop-WXYZ"


def test_visitor_key_unlocks_models_and_never_leaks(local_server, monkeypatch):
    import json

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers, "analyse", fake_analyse)
    m = out(local_server, "meta")
    assert not any(x["available"] for x in m["models"] if x["provider"] == "claude")
    local_server.set_inputs(set_keys={"claude": SECRET, "gemini": "", "nonce": 1})
    local_server.flush()
    m = out(local_server, "meta")
    assert all(x["available"] for x in m["models"] if x["provider"] == "claude")
    assert m["keys"]["claude"] == {"source": "you", "hint": "••••WXYZ", "server": False, "check": None}
    local_server.set_inputs(select_sample={"id": "scc", "nonce": 2})
    local_server.set_inputs(analyse={"models": [m["models"][0]["id"]], "nonce": 3})
    ws = wait_results(local_server, 1)
    assert ws["used"] == 0  # the visitor's own key does not consume the shared quota
    for name in ("meta", "workspace"):
        assert SECRET not in json.dumps(out(local_server, name)), name


def test_garbage_key_is_rejected(local_server):
    local_server.set_inputs(set_keys={"claude": "short", "gemini": "", "nonce": 1})
    local_server.flush()
    assert out(local_server, "meta")["keys"]["claude"]["source"] != "you"
