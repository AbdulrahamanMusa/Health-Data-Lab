"""Raw → Ready: an audit-ready cleaning workbench for health survey data.

Health Data Lab, week 1: "Never overwrite raw data — the cleaning log".
The server holds only computation and returns JSON; the UI is the React
client in src/ (built to www/ui.js). Uploaded files live in this session's
memory only: nothing is written to disk.
"""

import base64
from datetime import date, datetime

import pandas as pd
from shiny import reactive
from shiny.express import input, session
from shinyreact import reactive_output, send_message, set_react_page

from rtr import pipeline as P
from rtr import report
from rtr.sample import FORM_TITLE, sample_export

set_react_page()

MAX_UPLOAD_MB = 15


def _sample_raw():
    return P.raw_from_frame(sample_export(), "kobo_export_child_health_sample.csv", "sample")


raw = reactive.value(_sample_raw())
user_log = reactive.value([])  # reviewer decisions; append-only


@reactive.calc
def prepared():
    return P.prepare(raw())


@reactive.calc
def flags():
    return P.run_checks(prepared())


@reactive.calc
def full_log():
    return prepared().system_log + user_log()


@reactive.calc
def status():
    return P.flag_status(flags(), full_log())


@reactive.calc
def clean():
    return P.apply_log(prepared(), full_log())


@reactive.calc
def projected():
    return P.apply_log(prepared(), P.recommended_log(flags(), full_log()))


@reactive.calc
def raw_ind():
    return P.raw_indicators(raw(), prepared().columns)


@reactive.calc
def impact():
    cols = prepared().columns
    return P.impact(raw_ind(), P.indicators(clean(), cols), P.indicators(projected(), cols))


@reactive.calc
def enumerators():
    return P.enumerator_scorecard(prepared(), flags())


def reviewer() -> str:
    try:
        name = (input.reviewer() or "").strip()
    except Exception:  # noqa: BLE001 - input not sent yet
        name = ""
    return name or "Data manager"


# --------------------------------------------------------------- outputs


@reactive_output
def meta():
    return {
        "checks": [{"key": k, "label": v[0], "severity": v[1]} for k, v in P.CHECKS.items()],
        "actions": ["corrected", "set missing", "removed", "sent for verification", "kept as valid"],
    }


@reactive_output
def overview():
    fl, st = flags(), status()
    ready = P.readiness(fl, st)
    by_type = pd.Series([f["label"] for f in fl]).value_counts()
    open_by_type = pd.Series([f["label"] for f in fl if st[f["flag_id"]]["status"] == "open"]).value_counts()
    lga_col = prepared().columns.get("lga")
    by_lga = []
    if lga_col:
        base = prepared().base
        for lga, g in base.groupby(lga_col):
            rows = set(g["row"])
            n_flag = len({f["row"] for f in fl if f["row"] in rows})
            by_lga.append({"lga": str(lga), "records": int(len(g)), "flagged_pct": round(100 * n_flag / len(g), 1), "unmapped": bool(g["lga_code"].isna().all()) if "lga_code" in g else False})
        by_lga.sort(key=lambda r: -r["flagged_pct"])
    r = raw()
    return {
        "form": FORM_TITLE if r.source == "sample" else r.filename,
        "source": r.source,
        "filename": r.filename,
        "sha256": r.sha256,
        "received": r.received,
        "raw_rows": int(len(r.df)),
        "raw_cols": int(r.df.shape[1]),
        "readiness": ready,
        "funnel": P.funnel(r, prepared(), clean()),
        "projected_funnel": P.funnel(r, prepared(), projected()),
        "impact": impact(),
        "issues": [{"label": k, "total": int(v), "open": int(open_by_type.get(k, 0))} for k, v in by_type.items()],
        "by_lga": by_lga,
        "decisions": len([e for e in user_log() if e["action"] != "reverted"]),
        "attention": [e for e in enumerators() if e["status"] == "act now"][:4],
        "identifiers": prepared().identifiers,
    }


@reactive_output
def flag_list():
    f = input.flag_filter()
    fl, st = flags(), status()
    out = []
    for x in fl:
        s = st[x["flag_id"]]
        if f.get("check") and f["check"] != "all" and x["check"] != f["check"]:
            continue
        if f.get("severity") and f["severity"] != "all" and x["severity"] != f["severity"]:
            continue
        if f.get("status") and f["status"] != "all" and s["status"] != f["status"]:
            continue
        if f.get("enumerator") and f["enumerator"] != "all" and x["enumerator"] != f["enumerator"]:
            continue
        q = (f.get("q") or "").strip().lower()
        if q and q not in f"{x['record_id']} {x['row']} {x['detail']} {x['lga']}".lower():
            continue
        e = s["entry"]
        out.append({**x, "status": s["status"], "decision": None if e is None else {"action": e["action"], "new_value": e["new_value"], "reason": e["reason"], "by": e["changed_by"], "entry": e["entry"]}})
    groups = []
    for key, (label, sev) in P.CHECKS.items():
        items = [x for x in fl if x["check"] == key]
        if not items:
            continue
        open_items = [x for x in items if st[x["flag_id"]]["status"] == "open"]
        groups.append({"check": key, "label": label, "severity": sev, "total": len(items), "open": len(open_items), "rec_action": items[0]["rec_action"], "rec_reason": items[0]["rec_reason"]})
    return {
        "items": out[:400],
        "shown": len(out),
        "groups": groups,
        "enumerators": sorted({x["enumerator"] for x in fl if x["enumerator"]}),
        "counts": {s: sum(1 for x in fl if st[x["flag_id"]]["status"] == s) for s in ("open", "awaiting verification", "resolved")},
    }


@reactive_output
def cleaning_log():
    log = full_log()
    entries = [{**e, "check_label": P.CHECKS.get(e.get("check"), (None,))[0]} for e in log]
    entries.sort(key=lambda e: (e["changed_by"].startswith("system"), -abs(e["entry"])))
    user = [e for e in user_log()]
    return {
        "entries": entries[:600],
        "total": len(entries),
        "system": len(prepared().system_log),
        "user": len([e for e in user if e["action"] != "reverted"]),
        "reverted": len([e for e in user if e["action"] == "reverted"]),
        "by_action": pd.Series([e["action"] for e in active_entries()]).value_counts().to_dict() if active_entries() else {},
    }


def active_entries():
    return P.active(user_log())


@reactive_output
def enumerator_board():
    return {"rows": enumerators(), "team_median": enumerators()[0]["team_median"] if enumerators() else None}


@reactive_output
def dataset():
    r, p = raw(), prepared()
    return {
        "filename": r.filename,
        "source": r.source,
        "sha256": r.sha256,
        "received": r.received,
        "rows": int(len(r.df)),
        "cols": int(r.df.shape[1]),
        "profile": P.column_profile(r),
        "roles": {k: v for k, v in p.columns.items()},
        "identifiers": p.identifiers,
        "max_mb": MAX_UPLOAD_MB,
    }


# ---------------------------------------------------------------- events


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _append(entries: list[dict]):
    with reactive.isolate():
        current = list(user_log())
    start = max([e["entry"] for e in current] + [0]) + 1
    for i, e in enumerate(entries):
        e["entry"] = start + i
    user_log.set(current + entries)


def _entry(flag: dict, action: str, new_value, reason: str, verified: str = "") -> dict:
    return {
        "entry": 0,
        "row": flag["row"],
        "record_id": flag["record_id"],
        "flag_id": flag["flag_id"],
        "check": flag["check"],
        "variable": "ALL (record)" if action == "removed" else flag["variable"],
        "old_value": flag["value"],
        "new_value": "excluded from analysis" if action == "removed" else ("" if action in ("set missing",) else new_value),
        "reason": reason,
        "action": action,
        "verified_by_field": verified,
        "changed_by": reviewer(),
        "date": _now(),
        "reverted": False,
    }


async def toast(title, text="", level="ok"):
    await send_message(session, "toast", {"title": title, "text": text, "level": level})


@reactive.effect
@reactive.event(input.decide)
async def _decide():
    d = input.decide()
    if not d:
        return
    with reactive.isolate():
        fl = {f["flag_id"]: f for f in flags()}
        st = status()
    if d.get("flag_ids"):
        ids = d["flag_ids"]
    else:  # bulk: one check, or "__all__" open flags
        ids = [f["flag_id"] for f in fl.values() if st[f["flag_id"]]["status"] == "open" and d.get("check") in (f["check"], "__all__")]
    entries = []
    for fid in ids:
        f = fl.get(fid)
        if not f:
            continue
        if d["action"] == "recommended":
            entries.append(_entry(f, f["rec_action"], f["rec_new_value"], f["rec_reason"]))
        else:
            if d["action"] == "corrected" and not str(d.get("new_value") or "").strip():
                await toast("A corrected value is required", "Enter the new value before saving.", "danger")
                return
            reason = (d.get("reason") or "").strip()
            if not reason:
                await toast("A reason is required", "Every change in the cleaning log needs a reason.", "danger")
                return
            entries.append(_entry(f, d["action"], d.get("new_value"), reason))
    if entries:
        _append(entries)
        await toast(f"{len(entries)} decision{'s' if len(entries) > 1 else ''} logged", "The raw export is unchanged; the clean dataset was rebuilt from raw + log.")


@reactive.effect
@reactive.event(input.verify)
async def _verify():
    d = input.verify()
    if not d:
        return
    with reactive.isolate():
        f = next((x for x in flags() if x["flag_id"] == d["flag_id"]), None)
    if not f:
        return
    outcome = d["outcome"]
    note = (d.get("note") or "").strip() or "Field team confirmed"
    if outcome == "confirmed":
        e = _entry(f, "kept as valid", None, f"Field verification: value confirmed. {note}", "Y")
    elif outcome == "corrected":
        if not str(d.get("new_value") or "").strip():
            await toast("A corrected value is required", "", "danger")
            return
        e = _entry(f, "corrected", d["new_value"], f"Field verification: corrected. {note}", "Y")
    else:
        e = _entry(f, "removed", None, f"Field verification: could not be confirmed. {note}", "Y")
    _append([e])
    await toast("Field verification recorded", e["reason"])


@reactive.effect
@reactive.event(input.revert)
async def _revert():
    d = input.revert()
    if not d:
        return
    with reactive.isolate():
        current = list(user_log())
    target = next((e for e in current if e["entry"] == d["entry"] and not e["reverted"] and e["action"] != "reverted"), None)
    if not target:
        return
    updated = [{**e, "reverted": True} if e is target else e for e in current]
    reversal = {
        **target,
        "entry": 0,
        "action": "reverted",
        "old_value": target["new_value"],
        "new_value": target["old_value"],
        "reason": f"Reverted entry #{target['entry']} ({target['action']}). {(d.get('reason') or '').strip()}".strip(),
        "verified_by_field": "",
        "changed_by": reviewer(),
        "date": _now(),
        "reverted": False,
    }
    user_log.set(updated)
    _append([reversal])
    await toast(f"Entry #{target['entry']} reverted", "Nothing was erased: the reversal is itself logged.", "info")


@reactive.effect
@reactive.event(input.upload)
async def _upload():
    d = input.upload()
    if not d or not d.get("b64"):
        return
    try:
        content = base64.b64decode(d["b64"])
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"File is larger than {MAX_UPLOAD_MB} MB.")
        new_raw = P.load_raw(content, d.get("name") or "upload.csv")
        p = P.prepare(new_raw)
        P.run_checks(p)
    except Exception as e:  # noqa: BLE001 - report any parse problem to the user
        await toast("Could not read this file", str(e)[:200], "danger")
        return
    raw.set(new_raw)
    user_log.set([])
    found = [k for k, v in p.columns.items() if v]
    await toast("Export loaded", f"{len(new_raw.df):,} rows · recognised {len(found)} of {len(p.columns)} standard fields. Raw fingerprint saved.")


@reactive.effect
@reactive.event(input.use_sample)
async def _use_sample():
    if not input.use_sample():
        return
    raw.set(_sample_raw())
    user_log.set([])
    await toast("Sample survey loaded", "Child-health household survey in a fictional Demo State (synthetic).", "info")


@reactive.effect
@reactive.event(input.export)
async def _export():
    d = input.export()
    if not d:
        return
    with reactive.isolate():
        r, p, fl, st, lg, cl = raw(), prepared(), flags(), status(), full_log(), clean()
        en = enumerators()
        summary = {
            "final_n": int((cl["_status"] == "included").sum()),
            "readiness": P.readiness(fl, st),
            "impact": impact(),
            "funnel": P.funnel(r, p, cl),
            "issues_by_type": list(pd.Series([f["label"] for f in fl]).value_counts().items()),
        }
        who = reviewer()
        try:
            include_gps = bool(input.include_gps())
        except Exception:  # noqa: BLE001 - input not sent yet: default to the safer choice
            include_gps = False
    stem = r.filename.rsplit(".", 1)[0]
    stamp = date.today().isoformat()
    if d["kind"] == "audit":
        blob = report.audit_pack(r, p, fl, st, lg, cl, summary, en, include_gps)
        await send_message(session, "download", {"filename": f"{stem}_audit_pack_{stamp}.xlsx", "b64": base64.b64encode(blob).decode(), "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
    elif d["kind"] == "csv":
        csv = report.shareable(cl, p, fl, st, include_gps).to_csv(index=False)
        await send_message(session, "download", {"filename": f"{stem}_clean_{stamp}.csv", "text": csv, "mime": "text/csv"})
    elif d["kind"] == "html":
        await send_message(session, "download", {"filename": f"{stem}_cleaning_summary_{stamp}.html", "text": report.summary_html(r, summary, en, who), "mime": "text/html"})
    elif d["kind"] == "sample":
        await send_message(session, "download", {"filename": "kobo_export_child_health_sample.csv", "text": sample_export().to_csv(index=False), "mime": "text/csv"})
