import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from histo import images, prompt, providers, report

GOOD = {
    "image_assessment": {"is_histology": True, "stain": "H&E", "magnification": "intermediate", "quality": "adequate", "quality_notes": "In focus"},
    "tissue": {"site": "Skin", "tissue_type": "Squamous epithelium", "confidence": "high"},
    "classification": {"label": "malignant", "confidence": 88, "summary": "Infiltrating nests with keratin pearls."},
    "features": [{"name": "Keratin pearls", "observation": "Concentric keratin", "significance": "favours_malignant"}],
    "differential": [{"diagnosis": "Squamous cell carcinoma", "likelihood": "most_likely", "reason": "Keratinising nests"}],
    "teaching_points": ["Keratin pearls indicate squamous differentiation."],
    "next_steps": ["Assess depth of invasion on the full specimen."],
    "limitations": ["Single field of view."],
}


def walk(schema):
    if schema.get("type") == "object":
        yield schema
        for v in schema["properties"].values():
            yield from walk(v)
    elif schema.get("type") == "array":
        yield from walk(schema["items"])


def test_schema_is_strict_compatible():
    for obj in walk(prompt.SCHEMA):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_normalise_clamps_and_repairs():
    bad = json.loads(json.dumps(GOOD))
    bad["classification"].update(confidence=140, label="cancer")
    bad["features"][0]["significance"] = "??"
    out = prompt.normalise(bad)
    assert out["classification"]["confidence"] == 100 and out["classification"]["label"] == "indeterminate"
    assert out["features"][0]["significance"] == "neutral"


def jpeg_with_exif(size=(900, 600)) -> bytes:
    im = Image.new("RGB", size, (200, 120, 170))
    exif = Image.Exif()
    exif[0x010F] = "SecretScanner"  # Make
    exif[0x9286] = "Patient: Jane Doe"  # UserComment-like tag
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_prepare_strips_metadata_and_resizes():
    raw = jpeg_with_exif((3000, 2000))
    assert b"SecretScanner" in raw
    p = images.prepare(raw)
    assert b"SecretScanner" not in p.jpeg and b"Jane Doe" not in p.jpeg
    assert max(p.width, p.height) == images.MAX_EDGE
    assert not Image.open(io.BytesIO(p.jpeg)).getexif()


def test_prepare_rejects_bad_input():
    with pytest.raises(images.ImageError):
        images.prepare(b"not an image")
    small = io.BytesIO()
    Image.new("RGB", (50, 50)).save(small, "PNG")
    with pytest.raises(images.ImageError):
        images.prepare(small.getvalue())


def test_samples_have_licences_and_labels():
    s = images.samples()
    assert len(s) == 7
    for x in s:
        assert x["license"] and x["author"] and x["source_url"].startswith("https://commons.wikimedia.org")
        assert x["reference_label"] in ("benign", "malignant")
        assert x["thumb"].startswith("data:image/jpeg;base64,")


def test_agreement_and_reference_check():
    a = {"report": GOOD}
    b = {"report": {**GOOD, "classification": {**GOOD["classification"], "label": "benign"}}}
    assert report.agreement([a, a])["agree"] is True
    assert report.agreement([a, b])["agree"] is False
    assert report.reference_check("malignant", "malignant")["status"] == "agrees"
    assert report.reference_check("benign", "malignant")["status"] == "disagrees"
    assert report.reference_check("indeterminate", "malignant")["status"] == "uncommitted"


def test_report_escapes_model_text():
    evil = json.loads(json.dumps(GOOD))
    evil["classification"]["summary"] = "<script>alert(1)</script>"
    case = {"name": "x", "width": 1, "height": 1, "data_url": "data:", "reference": None}
    page = report.render(case, [{"label": "Claude", "model": "m", "report": evil}])
    assert "<script>alert" not in page and "&lt;script&gt;" in page


def test_missing_key_is_reported_not_raised(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    opt = providers.model_options()[0]
    r = providers.analyse(b"x", opt)
    assert "ANTHROPIC_API_KEY" in r["error"]


class FakeAnthropic:
    calls = []

    def __init__(self, *a, **k):
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeAnthropic.calls.append(kw)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(GOOD))],
            usage=SimpleNamespace(input_tokens=1500, output_tokens=700),
            model=kw["model"],
        )


def test_claude_request_shape(monkeypatch):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    opt = providers.model_options()[0]
    r = providers.analyse(images.sample_image("scc").jpeg, opt)
    assert r["report"]["classification"]["label"] == "malignant"
    kw = FakeAnthropic.calls[-1]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    img = kw["messages"][0]["content"][0]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg"
    assert "thinking" not in kw  # Opus 5.5: adaptive by default, never disabled


def test_claude_refusal_becomes_message(monkeypatch):
    import anthropic

    class Refuser(FakeAnthropic):
        def _create(self, **kw):
            return SimpleNamespace(stop_reason="refusal", content=[], usage=None, model=kw["model"])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(anthropic, "Anthropic", Refuser)
    r = providers.analyse(b"img", providers.model_options()[1])
    assert r["error"] == "Claude declined to analyse this image."


def test_gemini_request_shape(monkeypatch):
    from google import genai

    seen = {}

    class FakeModels:
        def generate_content(self, **kw):
            seen.update(kw)
            return SimpleNamespace(text=json.dumps(GOOD), usage_metadata=SimpleNamespace(prompt_token_count=900, candidates_token_count=400))

    class FakeClient:
        def __init__(self, api_key=None):
            seen["api_key"] = api_key
            self.models = FakeModels()

    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    monkeypatch.setattr(genai, "Client", FakeClient)
    opt = providers.model_options()[2]
    r = providers.analyse(images.sample_image("lipoma").jpeg, opt)
    assert r["report"]["tissue"]["site"] == "Skin" and seen["api_key"] == "g-test"
    assert seen["model"] == "gemini-3.8-flash"
    cfg = seen["config"]
    assert cfg.response_mime_type == "application/json" and cfg.response_json_schema == prompt.SCHEMA
