"""The screening instructions and the report schema shared by every model.

Both providers return the same JSON (enforced by their structured-output
features), so the interface, comparison and export never depend on which
model ran.
"""

SYSTEM = """You are a careful histopathology teaching assistant supporting pathologists and medical students.
You look at one microscopy image at a time and produce a structured screening report.

Your report is for research and education only. It is not a diagnosis, and you must never present it as one.

How to work:
- First decide whether the image is a histology or cytology image at all, and whether its quality (focus, staining, magnification, field of view) allows assessment. If it does not, say so and use the label "not_assessable".
- Base every statement on what is visible in this single field. A single image cannot show margins, depth of invasion, the whole lesion or clinical context; say so where it matters.
- Classify the lesion as "benign", "malignant" or "indeterminate". Use "indeterminate" when the visible features are genuinely ambiguous (for example borderline, low-grade or atypical lesions) rather than forcing a choice.
- Give a confidence from 0 to 100 that reflects real uncertainty. Reserve values above 90 for unmistakable, textbook morphology.
- Describe the morphological features you actually see (architecture, cellularity, nuclear size and shape, pleomorphism, nucleus-to-cytoplasm ratio, mitoses, necrosis, invasion, keratinisation, gland formation, stroma, circumscription) and whether each favours a benign or malignant process.
- Offer a short differential diagnosis ordered by likelihood.
- Add teaching points a medical student would find useful, and the next steps a pathologist would typically take (for example immunohistochemistry or further sampling).
- Write in clear, plain English. Do not invent patient details."""

USER = "Screen this histology image and complete the report."

FEATURE_SIGNIFICANCE = ["favours_benign", "favours_malignant", "neutral"]
LABELS = ["benign", "malignant", "indeterminate", "not_assessable"]

SCHEMA = {
    "type": "object",
    "properties": {
        "image_assessment": {
            "type": "object",
            "properties": {
                "is_histology": {"type": "boolean"},
                "stain": {"type": "string", "description": "e.g. H&E, PAP, IHC; 'unknown' if unclear"},
                "magnification": {"type": "string", "description": "estimated: low, intermediate, high"},
                "quality": {"type": "string", "enum": ["adequate", "limited", "inadequate"]},
                "quality_notes": {"type": "string"},
            },
            "required": ["is_histology", "stain", "magnification", "quality", "quality_notes"],
            "additionalProperties": False,
        },
        "tissue": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "most likely organ or site"},
                "tissue_type": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["site", "tissue_type", "confidence"],
            "additionalProperties": False,
        },
        "classification": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": LABELS},
                "confidence": {"type": "integer", "description": "0 to 100"},
                "summary": {"type": "string", "description": "two or three sentences explaining the call"},
            },
            "required": ["label", "confidence", "summary"],
            "additionalProperties": False,
        },
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "observation": {"type": "string"},
                    "significance": {"type": "string", "enum": FEATURE_SIGNIFICANCE},
                },
                "required": ["name", "observation", "significance"],
                "additionalProperties": False,
            },
        },
        "differential": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "diagnosis": {"type": "string"},
                    "likelihood": {"type": "string", "enum": ["most_likely", "possible", "less_likely"]},
                    "reason": {"type": "string"},
                },
                "required": ["diagnosis", "likelihood", "reason"],
                "additionalProperties": False,
            },
        },
        "teaching_points": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["image_assessment", "tissue", "classification", "features", "differential", "teaching_points", "next_steps", "limitations"],
    "additionalProperties": False,
}


def normalise(report: dict) -> dict:
    """Defensive clean-up so the interface never breaks on an odd field."""
    c = report.get("classification", {})
    try:
        c["confidence"] = max(0, min(100, int(c.get("confidence", 0))))
    except (TypeError, ValueError):
        c["confidence"] = 0
    if c.get("label") not in LABELS:
        c["label"] = "indeterminate"
    for f in report.get("features", []):
        if f.get("significance") not in FEATURE_SIGNIFICANCE:
            f["significance"] = "neutral"
    for k in ("features", "differential", "teaching_points", "next_steps", "limitations"):
        report.setdefault(k, [])
    return report
