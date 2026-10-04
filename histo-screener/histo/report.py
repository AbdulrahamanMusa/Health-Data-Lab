"""Printable screening report (HTML, print to PDF from the browser)."""

from __future__ import annotations

import html
from datetime import datetime

LABEL_TEXT = {"benign": "Benign", "malignant": "Malignant", "indeterminate": "Indeterminate", "not_assessable": "Not assessable"}
LABEL_COLOR = {"benign": "#0f766e", "malignant": "#9f1239", "indeterminate": "#b45309", "not_assessable": "#475569"}
SIG_TEXT = {"favours_benign": "favours benign", "favours_malignant": "favours malignant", "neutral": "neutral"}


def agreement(results: list[dict]) -> dict | None:
    labels = [r["report"]["classification"]["label"] for r in results if r.get("report")]
    if len(labels) < 2:
        return None
    return {"agree": len(set(labels)) == 1, "labels": labels}


def reference_check(label: str, reference_label: str | None) -> dict | None:
    if not reference_label:
        return None
    if label in ("indeterminate", "not_assessable"):
        return {"status": "uncommitted", "text": f"The model did not commit (reference: {reference_label})."}
    ok = label == reference_label
    return {"status": "agrees" if ok else "disagrees", "text": f"{'Agrees' if ok else 'Disagrees'} with the reference label ({reference_label})."}


def render(case: dict, results: list[dict]) -> str:
    e = html.escape
    blocks = []
    for r in results:
        if not r.get("report"):
            blocks.append(f"<section><h2>{e(r['label'])}</h2><p class='err'>{e(r.get('error', 'No result'))}</p></section>")
            continue
        rep = r["report"]
        c = rep["classification"]
        color = LABEL_COLOR[c["label"]]
        feats = "".join(f"<tr><td><b>{e(f['name'])}</b></td><td>{e(f['observation'])}</td><td>{e(SIG_TEXT[f['significance']])}</td></tr>" for f in rep["features"])
        diff = "".join(f"<li><b>{e(d['diagnosis'])}</b> ({e(d['likelihood'].replace('_', ' '))}): {e(d['reason'])}</li>" for d in rep["differential"])
        lst = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs)  # noqa: E731
        ia, t = rep["image_assessment"], rep["tissue"]
        blocks.append(f"""<section>
<h2>{e(r['label'])} <small>{e(r['model'])}</small></h2>
<div class="verdict" style="border-color:{color}"><span style="background:{color}">{LABEL_TEXT[c['label']]}</span> <b>{c['confidence']}% confidence</b><p>{e(c['summary'])}</p></div>
<p class="meta">Image: {e(ia['stain'])}, {e(ia['magnification'])} magnification, quality {e(ia['quality'])} ({e(ia['quality_notes'])}). Tissue: {e(t['tissue_type'])}, {e(t['site'])} ({e(t['confidence'])} confidence).</p>
<h3>Morphological features</h3><table>{feats}</table>
<h3>Differential diagnosis</h3><ol>{diff}</ol>
<h3>Teaching points</h3><ul>{lst(rep['teaching_points'])}</ul>
<h3>Suggested next steps</h3><ul>{lst(rep['next_steps'])}</ul>
<h3>Limitations</h3><ul>{lst(rep['limitations'])}</ul>
</section>""")
    ref = ""
    if case.get("reference"):
        ref = f"<p class='meta'>Reference label for this teaching image: <b>{e(case['reference']['reference_diagnosis'])}</b> ({e(case['reference']['reference_label'])}). Image: {e(case['reference']['author'])}, {e(case['reference']['license'])}, via Wikimedia Commons.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Histopathology screening report — {e(case['name'])}</title>
<style>body{{font:14px/1.55 Georgia,'Times New Roman',serif;color:#1f1724;max-width:860px;margin:32px auto;padding:0 22px}}
h1{{font:600 22px system-ui,sans-serif;margin:0}}h2{{font:600 17px system-ui,sans-serif;margin:28px 0 8px;border-bottom:2px solid #5b2a6e;padding-bottom:4px}}h2 small{{font-weight:400;color:#6b5b73;font-size:12px}}
h3{{font:600 13px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.05em;color:#5b2a6e;margin:16px 0 6px}}
.meta{{color:#5c5163;font-size:13px}}.verdict{{border-left:5px solid;padding:8px 12px;background:#faf6fb;margin:8px 0}}.verdict span{{color:#fff;padding:2px 9px;border-radius:4px;font:600 12px system-ui;margin-right:8px}}
table{{border-collapse:collapse;width:100%}}td{{border-bottom:1px solid #e9e1ec;padding:5px 6px;vertical-align:top}}img{{max-width:100%;border-radius:6px}}
.err{{color:#9f1239}}.disclaimer{{margin-top:28px;padding:10px 12px;border:1px solid #e9d5db;background:#fff7f9;font:12px system-ui;color:#5c5163}}</style></head><body>
<h1>Histopathology screening report</h1>
<p class="meta">{e(case['name'])} · {case['width']}×{case['height']} px · generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<img src="{case['data_url']}" alt="Screened image">
{ref}
{''.join(blocks)}
<div class="disclaimer"><b>For research and education only.</b> This AI-generated screening report is not a medical diagnosis and must not be used for clinical decisions. Diagnosis requires a qualified pathologist reviewing the full specimen with clinical context.</div>
</body></html>"""
