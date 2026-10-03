"""Exports: audit pack (.xlsx), shareable clean dataset (.csv), one-page summary (.html).

The cleaning-log sheet uses the exact columns of the health-data-management
cleaning_log_template.xlsx, so it drops straight into an existing workflow.
"""

from __future__ import annotations

import html
import io
from datetime import date, datetime

import pandas as pd

from .pipeline import CHECKS, Prepared, Raw

TEMPLATE_COLUMNS = [
    "record_id",
    "variable",
    "old_value",
    "new_value",
    "reason",
    "action (corrected/flagged/set missing/removed)",
    "verified_by_field (Y/N)",
    "changed_by",
    "date",
]
_ACTION_MAP = {
    "corrected": "corrected",
    "set missing": "set missing",
    "removed": "removed",
    "sent for verification": "flagged",
    "kept as valid": "flagged",
    "reverted": "reverted",
}


def log_frame(log: list[dict]) -> pd.DataFrame:
    rows = []
    for e in log:
        rows.append(
            {
                "record_id": e["record_id"],
                "variable": e["variable"],
                "old_value": e["old_value"],
                "new_value": e["new_value"],
                "reason": e["reason"],
                "action (corrected/flagged/set missing/removed)": _ACTION_MAP.get(e["action"], e["action"]),
                "verified_by_field (Y/N)": e.get("verified_by_field") or ("N" if e["action"] == "sent for verification" else ""),
                "changed_by": e["changed_by"],
                "date": e["date"],
                # Extra audit columns beyond the template:
                "entry": e["entry"],
                "raw_row": e["row"],
                "check": CHECKS.get(e.get("check"), (e.get("check"),))[0],
                "decision": e["action"],
                "status": "reverted" if e.get("reverted") else "active",
            }
        )
    return pd.DataFrame(rows, columns=TEMPLATE_COLUMNS + ["entry", "raw_row", "check", "decision", "status"])


def shareable(clean: pd.DataFrame, p: Prepared, flags: list[dict], status: dict, include_gps: bool) -> pd.DataFrame:
    """Analysis rows only, no direct identifiers, pending issues noted per record."""
    d = clean[clean["_status"] == "included"].copy()
    pending: dict[int, list[str]] = {}
    for f in flags:
        if status[f["flag_id"]]["status"] != "resolved":
            pending.setdefault(f["row"], []).append(f["label"])
    d["qa_open_issues"] = d["row"].map(lambda r: "; ".join(pending.get(int(r), [])))
    drop = ["_status", "_exclusion_reason"] + [c for c in d.columns if c.startswith("_") and c not in ("_uuid", "_submission_time")]
    if not include_gps:
        drop += [c for c in (p.columns.get("lat"), p.columns.get("lon")) if c]
    return d.drop(columns=[c for c in drop if c in d.columns])


def audit_pack(raw: Raw, p: Prepared, flags: list[dict], status: dict, log: list[dict], clean: pd.DataFrame, summary: dict, enumerators: list[dict], include_gps: bool) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        s = [
            ("Source file", raw.filename),
            ("Raw SHA-256 fingerprint", raw.sha256),
            ("Received", raw.received),
            ("Records received", len(raw.df)),
            ("Final analysis records", summary["final_n"]),
            ("Readiness", summary["readiness"]["verdict"]),
            ("Flags resolved (%)", summary["readiness"]["score"]),
            ("Exported", datetime.now().isoformat(timespec="seconds")),
            ("Household GPS included", "yes" if include_gps else "no (removed for sharing)"),
        ]
        pd.DataFrame(s, columns=["item", "value"]).to_excel(w, sheet_name="summary", index=False)
        shareable(clean, p, flags, status, include_gps).to_excel(w, sheet_name="clean_data", index=False)
        log_frame(log).to_excel(w, sheet_name="cleaning_log", index=False)
        fl = pd.DataFrame(flags)
        if len(fl):
            fl["status"] = fl["flag_id"].map(lambda i: status[i]["status"])
            fl = fl[["row", "record_id", "enumerator", "lga", "label", "severity", "variable", "value", "detail", "rec_action", "rec_reason", "status"]]
        fl.to_excel(w, sheet_name="flags", index=False)
        pd.DataFrame(enumerators).drop(columns=["follow_up"], errors="ignore").assign(
            follow_up=[", ".join(e["follow_up"]) for e in enumerators]
        ).to_excel(w, sheet_name="enumerators", index=False)
        pd.DataFrame([{**{"indicator": r["label"], "definition": r["definition"]}, "raw": r["raw"]["value"], "clean_now": r["clean"]["value"], "after_recommendations": r["projected"]["value"], "bias_points": r["bias"]} for r in summary["impact"]]).to_excel(w, sheet_name="indicator_impact", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            ws.freeze_panes = "A2"
    return buf.getvalue()


def summary_html(raw: Raw, summary: dict, enumerators: list[dict], reviewer: str) -> str:
    e = html.escape
    r = summary["readiness"]
    color = {"not ready": "#b91c1c", "ready with caveats": "#b45309", "ready": "#15803d"}[r["verdict"]]
    funnel = "".join(f"<tr><td>{e(s['label'])}</td><td class='n'>{s['n']:+,}</td></tr>" if not s.get("final") and i else f"<tr class='{'final' if s.get('final') else ''}'><td>{e(s['label'])}</td><td class='n'>{s['n']:,}</td></tr>" for i, s in enumerate(summary["funnel"]))
    impact = "".join(
        f"<tr><td><b>{e(x['label'])}</b><br><small>{e(x['definition'])}</small></td><td class='n'>{x['raw']['value']}%</td><td class='n'>{x['projected']['value']}%</td><td class='n'><b>{x['bias']:+.1f}</b></td></tr>"
        for x in summary["impact"]
        if x["raw"]["value"] is not None and x["projected"]["value"] is not None
    )
    issues = "".join(f"<tr><td>{e(k)}</td><td class='n'>{v}</td></tr>" for k, v in summary["issues_by_type"])
    enums = "".join(f"<tr><td>{e(x['enumerator'])}</td><td class='n'>{x['interviews']}</td><td class='n'>{x['flagged_pct']}%</td><td>{e('; '.join(x['follow_up']) or '—')}</td></tr>" for x in enumerators if x["status"] != "good")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Cleaning summary — {e(raw.filename)}</title>
<style>body{{font:13px/1.5 Segoe UI,system-ui,sans-serif;color:#0f172a;max-width:900px;margin:28px auto;padding:0 20px}}
h1{{font-size:20px;margin:0}}h2{{font-size:14px;margin:22px 0 6px;color:#0f766e}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #e5e7eb;padding:5px 8px;text-align:left;vertical-align:top}}th{{font-size:11px;text-transform:uppercase;color:#64748b}}
.n{{text-align:right;font-variant-numeric:tabular-nums}}.final td{{font-weight:700;border-top:2px solid #0f172a}}small{{color:#64748b}}
.verdict{{display:inline-block;padding:6px 12px;border-radius:6px;color:#fff;background:{color};font-weight:700;text-transform:uppercase;font-size:12px}}
.meta{{color:#64748b;font-size:12px}}code{{font-size:11px}}@media print{{body{{margin:0}}}}</style></head><body>
<h1>Data cleaning summary</h1>
<p class="meta">{e(raw.filename)} · received {e(raw.received[:16].replace('T', ' '))} · prepared by {e(reviewer)} on {date.today().isoformat()}<br>
Raw file fingerprint (SHA-256): <code>{raw.sha256}</code> — the raw export was not modified.</p>
<p><span class="verdict">{e(r['verdict'])}</span> &nbsp;{e(r['reason'])}</p>
<h2>Records: received → excluded → final</h2><table>{funnel}</table>
<h2>Why cleaning matters: indicators before and after</h2>
<table><tr><th>Indicator</th><th class="n">Raw export</th><th class="n">After cleaning</th><th class="n">Difference (pts)</th></tr>{impact}</table>
<h2>Issues found by type</h2><table>{issues}</table>
<h2>Supervision follow-up</h2><table><tr><th>Enumerator</th><th class="n">Interviews</th><th class="n">Flagged</th><th>Recommended follow-up</th></tr>{enums or '<tr><td colspan=4>No follow-up needed.</td></tr>'}</table>
<h2>Outstanding</h2><p>{r['open']['critical'] + r['open']['high'] + r['open']['medium'] + r['open']['low']} flags without a decision · {r['waiting']} records awaiting field verification.</p>
<p class="meta">Generated by Raw → Ready (Health Data Lab). Every change is listed in the cleaning log of the audit pack.</p>
</body></html>"""
