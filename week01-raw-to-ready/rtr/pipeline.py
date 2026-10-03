"""Raw → Ready cleaning engine.

The design rule is the first principle of health data management: the raw
export is never modified. Everything downstream is recomputed as

    clean = apply(prepare(raw), cleaning_log)

so any number in the app can be reproduced from the raw file plus the log, and
any decision can be reversed by appending to the log (never by erasing it).
Checks and recommended actions follow references/primary-data-cleaning.md.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from .sample import LGA_NAME_TO_CODE

# ----------------------------------------------------------------- raw data


@dataclass(frozen=True)
class Raw:
    df: pd.DataFrame  # exactly as received; never mutated
    sha256: str
    filename: str
    received: str
    source: str  # "sample" or "upload"


def load_raw(content: bytes, filename: str, source: str = "upload") -> Raw:
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), dtype=object)
    else:
        text = content.decode("utf-8-sig", errors="replace")
        sep = ";" if text[:3000].count(";") > text[:3000].count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=object, keep_default_na=True)
    if df.empty:
        raise ValueError("The file has no data rows.")
    return Raw(df=df, sha256=hashlib.sha256(content).hexdigest(), filename=filename, received=datetime.now().isoformat(timespec="seconds"), source=source)


def raw_from_frame(df: pd.DataFrame, filename: str, source: str) -> Raw:
    content = df.to_csv(index=False).encode("utf-8")
    return Raw(df=df.copy(), sha256=hashlib.sha256(content).hexdigest(), filename=filename, received=datetime.now().isoformat(timespec="seconds"), source=source)


# ------------------------------------------------------------ preparation

IDENTIFIER_PATTERN = re.compile(r"(^|_)(name|full_?name|respondent_name|phone|tel|telephone|mobile|nin|national_id|address|email)($|_)", re.I)

# Columns the checks understand, with the names Kobo forms commonly use.
ALIASES = {
    "enumerator": ["username", "enumerator", "enumerator_id", "enum_id", "_submitted_by"],
    "consent": ["consent", "consent_given", "informed_consent"],
    "lga": ["lga", "lga_name", "local_government_area"],
    "ward": ["ward", "ward_name"],
    "hh_id": ["hh_id", "household_id", "hhid"],
    "lat": ["_gps_latitude", "_geopoint_latitude", "_location_latitude", "latitude", "gps_latitude", "lat"],
    "lon": ["_gps_longitude", "_geopoint_longitude", "_location_longitude", "longitude", "gps_longitude", "lon"],
    "age_months": ["child_age_months", "age_months", "child_age"],
    "muac": ["muac_cm", "muac"],
    "oedema": ["oedema", "bilateral_oedema", "edema"],
    "penta1": ["penta1", "penta_1", "dpt1"],
    "penta3": ["penta3", "penta_3", "dpt3"],
    "anc_attended": ["anc_attended", "attended_anc", "anc_any"],
    "anc_visits": ["anc_visits", "anc_number", "num_anc_visits"],
}


def _find(cols: list[str], names: list[str]) -> str | None:
    low = {c.lower(): c for c in cols}
    return next((low[n] for n in names if n in low), None)


def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


_LGA_KEYS = {_norm(n): n for n in LGA_NAME_TO_CODE} | {
    "egbeda": "Egbeda Nla",
    "egbedan": "Egbeda Nla",
}


def _system_entry(seq: int, record, row, variable, old, new, reason, action) -> dict:
    return {
        "entry": seq,
        "row": row,
        "record_id": record,
        "flag_id": None,
        "check": "system",
        "variable": variable,
        "old_value": old,
        "new_value": new,
        "reason": reason,
        "action": action,
        "verified_by_field": "",
        "changed_by": "system (standard rule)",
        "date": datetime.now().isoformat(timespec="seconds"),
        "reverted": False,
    }


@dataclass
class Prepared:
    base: pd.DataFrame  # analysis copy: structured, de-duplicated, identifiers removed
    columns: dict  # role -> column name
    identifiers: list[str]
    system_log: list[dict]
    exact_duplicates: int


def prepare(raw: Raw) -> Prepared:
    df = raw.df.copy()
    log: list[dict] = []
    seq = 0

    def add(*args):
        nonlocal seq
        seq += 1
        log.append(_system_entry(-seq, *args))

    # Kobo group prefixes ("child/muac_cm") → question names, kept unique.
    new_cols, seen = [], set()
    for c in df.columns:
        short = str(c).split("/")[-1].strip()
        short = short if short not in seen else str(c).replace("/", "__")
        seen.add(short)
        new_cols.append(short)
    df.columns = new_cols
    # Names this engine uses internally; an incoming column with the same name keeps its data under a new name.
    df = df.rename(columns={c: f"{c}_in_file" for c in ("row", "record_id", "lga_code") if c in df.columns})
    df.insert(0, "row", np.arange(1, len(df) + 1))  # position in the raw file
    id_col = _find(list(df.columns), ["_uuid", "meta_instanceid", "instanceid", "_id", "key"])
    df.insert(1, "record_id", df[id_col].astype(str) if id_col else df["row"].map(lambda r: f"row-{r}"))
    cols = {role: _find(list(df.columns), names) for role, names in ALIASES.items()}

    # Whitespace in text answers.
    for c in df.columns:
        if df[c].dtype == object:
            s = df[c]
            stripped = s.where(s.isna(), s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True))
            n = int((s.notna() & (s.astype(str) != stripped.astype(str))).sum())
            if n:
                add("ALL", None, c, f"{n} values with extra spaces", "trimmed", f"Trimmed leading/trailing spaces in {n} values", "corrected")
            df[c] = stripped

    # Numbers that arrived as text.
    for role in ("lat", "lon", "age_months", "muac", "anc_visits"):
        c = cols.get(role)
        if c:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # LGA names → official codes (join on codes, never names).
    if cols.get("lga"):
        c = cols["lga"]
        std = df[c].map(lambda v: _LGA_KEYS.get(_norm(v)) if pd.notna(v) else None)
        changed = df[c].notna() & std.notna() & (std != df[c])
        if changed.any():
            variants = sorted(set(df.loc[changed, c].astype(str)))
            add("ALL", None, c, ", ".join(variants[:6]) + ("…" if len(variants) > 6 else ""), "master-list spelling", f"Standardised {int(changed.sum())} LGA spellings to the master list", "corrected")
        df[c] = std.where(std.notna(), df[c])
        df["lga_code"] = std.map(LGA_NAME_TO_CODE)

    # Direct identifiers stay in the raw file only.
    identifiers = [c for c in df.columns if IDENTIFIER_PATTERN.search(c)]
    if identifiers:
        add("ALL", None, ", ".join(identifiers), "present", "removed from analysis copy", "Direct identifiers kept in raw only (data minimisation, NDPA)", "removed")
        df = df.drop(columns=identifiers)

    # Exact duplicates: identical answers, re-sent with new system fields.
    content = [c for c in df.columns if not c.startswith("_") and c not in ("row", "record_id")]
    dup = df.duplicated(subset=content, keep="first")
    for _, r in df[dup].iterrows():
        add(r["record_id"], int(r["row"]), "ALL", "record", "removed", "Exact duplicate submission (same answers re-sent)", "removed")
    df = df[~dup].reset_index(drop=True)
    return Prepared(base=df, columns=cols, identifiers=identifiers, system_log=log, exact_duplicates=int(dup.sum()))


# ------------------------------------------------------------------ checks

CHECKS = {
    "duplicate_id": ("Duplicate submission ID", "high"),
    "duplicate_household": ("Household interviewed twice", "medium"),
    "no_consent": ("No informed consent", "critical"),
    "desk_interview": ("Suspected desk interview", "critical"),
    "short_interview": ("Interview too short", "high"),
    "long_interview": ("Interview unusually long", "low"),
    "out_of_hours": ("Interview outside 06:00–20:00", "medium"),
    "missing_gps": ("GPS not captured", "low"),
    "age_range": ("Child age out of range", "high"),
    "muac_range": ("MUAC out of range", "high"),
    "penta_inconsistent": ("Penta3 without Penta1", "medium"),
    "anc_inconsistent": ("ANC visits but 'never attended'", "medium"),
    "anc_range": ("Implausible number of ANC visits", "high"),
    "lga_unmapped": ("LGA not in master list", "high"),
}
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _flag(r, check, variable, value, detail, action, reason, new_value=None) -> dict:
    label, severity = CHECKS[check]
    return {
        "flag_id": f"{check}:{int(r['row'])}",
        "row": int(r["row"]),
        "record_id": r["record_id"],
        "check": check,
        "label": label,
        "severity": severity,
        "variable": variable,
        "value": None if value is None or (isinstance(value, float) and np.isnan(value)) else str(value),
        "detail": detail,
        "rec_action": action,
        "rec_new_value": None if new_value is None else str(new_value),
        "rec_reason": reason,
    }


def run_checks(p: Prepared) -> list[dict]:
    df, c = p.base, p.columns
    flags: list[dict] = []
    enum = c.get("enumerator")

    # Edited resubmissions: same ID, different answers → keep the latest.
    if "_uuid" in df.columns:
        order = df.sort_values("_submission_time" if "_submission_time" in df.columns else "row")
        for _, g in order[order["_uuid"].duplicated(keep=False)].groupby("_uuid"):
            latest = g.iloc[-1]
            for _, r in g.iloc[:-1].iterrows():
                flags.append(_flag(r, "duplicate_id", "_uuid", r["_uuid"], f"Superseded by row {int(latest['row'])} submitted later", "removed", "Earlier version of an edited resubmission; keeping the latest"))

    if c.get("hh_id"):
        d = df[df[c["hh_id"]].duplicated(keep=False) & df[c["hh_id"]].notna()]
        if "_uuid" in df.columns:
            d = d[~d["_uuid"].duplicated(keep=False)]
        for _, r in d.iterrows():
            flags.append(_flag(r, "duplicate_household", c["hh_id"], r[c["hh_id"]], "Same household ID appears in another interview", "sent for verification", "Confirm with team leads whether this is one household or a mis-typed ID"))

    if c.get("consent"):
        for _, r in df[df[c["consent"]].astype(str).str.lower().ne("yes")].iterrows():
            flags.append(_flag(r, "no_consent", c["consent"], r[c["consent"]], "Answers recorded although consent was not given", "removed", "No informed consent: exclude from analysis (kept in raw)"))

    if {"start", "end"} <= set(df.columns):
        st = pd.to_datetime(df["start"], errors="coerce")
        en = pd.to_datetime(df["end"], errors="coerce")
        dur = (en - st).dt.total_seconds() / 60
        df = df.assign(_duration=dur)
        med = float(dur.median())
        if med > 0:
            for _, r in df[dur < med / 3].iterrows():
                flags.append(_flag(r, "short_interview", "duration", f"{r['_duration']:.1f} min", f"{r['_duration']:.1f} min vs median {med:.0f} min", "sent for verification", "Too short to have covered the questionnaire: call back the household"))
            for _, r in df[dur > 3 * med].iterrows():
                flags.append(_flag(r, "long_interview", "duration", f"{r['_duration']:.0f} min", f"{r['_duration']:.0f} min vs median {med:.0f} min", "kept as valid", "Often a form left open on the tablet; no effect on answers"))
        hour = st.dt.hour
        for _, r in df[(hour < 6) | (hour >= 20)].iterrows():
            flags.append(_flag(r, "out_of_hours", "start", r["start"], f"Started at {str(r['start'])[11:16]}", "sent for verification", "Household visits at night are unlikely: confirm with the supervisor"))

    if c.get("lat") and c.get("lon"):
        lat, lon = df[c["lat"]], df[c["lon"]]
        for _, r in df[lat.isna() | lon.isna()].iterrows():
            flags.append(_flag(r, "missing_gps", c["lat"], None, "No coordinates captured", "kept as valid", "Keep the interview; note GPS coverage as a limitation"))
        pts = lat.round(5).astype(str) + "," + lon.round(5).astype(str)
        counts = pts.map(pts.value_counts())
        for _, r in df[lat.notna() & (counts >= 3)].iterrows():
            flags.append(_flag(r, "desk_interview", c["lat"], f"{r[c['lat']]:.5f}, {r[c['lon']]:.5f}", f"Same coordinates as {int(counts[r.name]) - 1} other interviews", "removed", "Suspected fabrication: exclude pending supervisor review (never delete quietly)"))

    if c.get("age_months"):
        a = df[c["age_months"]]
        for _, r in df[a.notna() & ~a.between(0, 59)].iterrows():
            flags.append(_flag(r, "age_range", c["age_months"], int(r[c["age_months"]]), "Child age must be 0–59 months", "set missing", "Impossible for this survey and cannot be verified: set to missing"))

    if c.get("muac"):
        m = df[c["muac"]]
        for _, r in df[m.notna() & ~m.between(6, 26)].iterrows():
            v = float(r[c["muac"]])
            if 60 <= v <= 260:
                flags.append(_flag(r, "muac_range", c["muac"], v, f"{v:g} looks like millimetres", "corrected", "MUAC recorded in mm; converted to cm", new_value=round(v / 10, 1)))
            else:
                flags.append(_flag(r, "muac_range", c["muac"], v, "Valid MUAC is 6–26 cm", "set missing", "Impossible MUAC that cannot be corrected with confidence: set to missing"))

    if c.get("penta1") and c.get("penta3"):
        bad = df[c["penta3"]].astype(str).str.lower().eq("yes") & df[c["penta1"]].astype(str).str.lower().eq("no")
        for _, r in df[bad].iterrows():
            flags.append(_flag(r, "penta_inconsistent", c["penta3"], "yes", "Penta3 = yes but Penta1 = no", "sent for verification", "Check the vaccination card on call-back"))

    if c.get("anc_visits"):
        v = df[c["anc_visits"]]
        for _, r in df[v.notna() & (v > 20)].iterrows():
            flags.append(_flag(r, "anc_range", c["anc_visits"], int(r[c["anc_visits"]]), "More than 20 ANC visits is implausible", "set missing", "Implausible and unverifiable: set to missing"))
        if c.get("anc_attended"):
            bad = df[c["anc_attended"]].astype(str).str.lower().eq("no") & (v > 0)
            for _, r in df[bad].iterrows():
                flags.append(_flag(r, "anc_inconsistent", c["anc_visits"], int(r[c["anc_visits"]]), "Visits recorded but 'never attended ANC'", "sent for verification", "Confirm with the mother which answer is right"))

    if "lga_code" in df.columns and c.get("lga"):
        for _, r in df[df["lga_code"].isna()].iterrows():
            flags.append(_flag(r, "lga_unmapped", c["lga"], r[c["lga"]], f"'{r[c['lga']]}' is not an LGA in the master list", "sent for verification", "Ask the team which LGA; use the ward and GPS to confirm"))

    for f in flags:
        f["enumerator"] = df.loc[df["row"] == f["row"], enum].iat[0] if enum else None
        f["lga"] = df.loc[df["row"] == f["row"], c["lga"]].iat[0] if c.get("lga") else None
    return sorted(flags, key=lambda f: (SEVERITY_RANK[f["severity"]], f["check"], f["row"]))


# ------------------------------------------------------------ decisions


def active(log: list[dict]) -> list[dict]:
    return [e for e in log if not e["reverted"] and e["action"] != "reverted"]


def flag_status(flags: list[dict], log: list[dict]) -> dict[str, dict]:
    """Latest active decision for each flag: open, resolved or awaiting verification."""
    latest: dict[str, dict] = {}
    for e in active(log):
        if e.get("flag_id"):
            latest[e["flag_id"]] = e
    out = {}
    for f in flags:
        e = latest.get(f["flag_id"])
        if e is None:
            out[f["flag_id"]] = {"status": "open", "entry": None}
        elif e["action"] == "sent for verification" and e.get("verified_by_field") != "Y":
            out[f["flag_id"]] = {"status": "awaiting verification", "entry": e}
        else:
            out[f["flag_id"]] = {"status": "resolved", "entry": e}
    return out


def apply_log(p: Prepared, log: list[dict]) -> pd.DataFrame:
    """Rebuild the clean dataset from the prepared copy and the decisions."""
    df = p.base.copy()
    df["_status"] = "included"
    df["_exclusion_reason"] = ""
    pos = {int(r): i for i, r in enumerate(df["row"])}
    for e in active(log):
        if e["changed_by"].startswith("system") or e["row"] is None:
            continue
        i = pos.get(int(e["row"]))
        if i is None:
            continue
        idx = df.index[i]
        if e["action"] == "removed":
            df.at[idx, "_status"] = "excluded"
            df.at[idx, "_exclusion_reason"] = CHECKS[e["check"]][0] if e.get("check") in CHECKS else (e["reason"] or "Excluded by reviewer")
        elif e["action"] == "set missing" and e["variable"] in df.columns:
            df.at[idx, e["variable"]] = np.nan
        elif e["action"] == "corrected" and e["variable"] in df.columns and e["new_value"] not in (None, ""):
            col = df[e["variable"]]
            df.at[idx, e["variable"]] = pd.to_numeric(e["new_value"], errors="coerce") if pd.api.types.is_numeric_dtype(col) else e["new_value"]
    return df


def recommended_log(flags: list[dict], log: list[dict], who: str = "projection") -> list[dict]:
    """The log plus the recommended action for every still-open flag."""
    status = flag_status(flags, log)
    extra = [
        {"entry": 10**9 + i, "row": f["row"], "record_id": f["record_id"], "flag_id": f["flag_id"], "check": f["check"], "variable": f["variable"], "old_value": f["value"], "new_value": f["rec_new_value"], "reason": f["rec_reason"], "action": f["rec_action"], "verified_by_field": "", "changed_by": who, "date": "", "reverted": False}
        for i, f in enumerate(flags)
        if status[f["flag_id"]]["status"] == "open"
    ]
    return log + extra


# ------------------------------------------------------------- indicators


def _yes(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().eq("yes")


def indicators(df: pd.DataFrame, cols: dict, include_all: bool = False) -> dict:
    """Headline indicators (definitions from references/indicators.md)."""
    d = df if include_all or "_status" not in df.columns else df[df["_status"] == "included"]
    out = {"records": int(len(d))}
    age = pd.to_numeric(d[cols["age_months"]], errors="coerce") if cols.get("age_months") else None
    if age is not None and cols.get("penta3"):
        kids = d[age.between(12, 23)]
        p3 = kids[cols["penta3"]].dropna()
        out["penta3"] = {"num": int(_yes(p3).sum()), "den": int(len(p3)), "value": round(100 * _yes(p3).mean(), 1) if len(p3) else None}
        if cols.get("penta1"):
            p1n = int(_yes(kids[cols["penta1"]].dropna()).sum())
            out["dropout"] = {"num": p1n - out["penta3"]["num"], "den": p1n, "value": round(100 * (p1n - out["penta3"]["num"]) / p1n, 1) if p1n else None}
    if age is not None and cols.get("muac"):
        m = pd.to_numeric(d[cols["muac"]], errors="coerce")
        oed = _yes(d[cols["oedema"]]) if cols.get("oedema") else pd.Series(False, index=d.index)
        measured = age.between(6, 59) & m.notna()
        gam = measured & ((m < 12.5) | oed)
        sam = measured & ((m < 11.5) | oed)
        n = int(measured.sum())
        out["gam"] = {"num": int(gam.sum()), "den": n, "value": round(100 * gam.sum() / n, 1) if n else None}
        out["sam"] = {"num": int(sam.sum()), "den": n, "value": round(100 * sam.sum() / n, 1) if n else None}
    if cols.get("anc_visits"):
        v = pd.to_numeric(d[cols["anc_visits"]], errors="coerce").dropna()
        out["anc4"] = {"num": int((v >= 4).sum()), "den": int(len(v)), "value": round(100 * (v >= 4).mean(), 1) if len(v) else None}
    return out


def raw_indicators(raw: Raw, cols: dict) -> dict:
    """Indicators computed naively on the export as received: what you get without cleaning."""
    df = raw.df.copy()
    df.columns = [str(c).split("/")[-1].strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    for role in ("age_months", "muac", "anc_visits"):
        if cols.get(role) in df.columns:
            df[cols[role]] = pd.to_numeric(df[cols[role]], errors="coerce")
    return indicators(df, cols, include_all=True)


INDICATOR_META = [
    ("penta3", "Penta3 coverage", "Children 12–23 months who received Penta3", "up"),
    ("dropout", "Penta1→3 dropout", "Children who started but did not finish the series", "down"),
    ("gam", "Global acute malnutrition (MUAC)", "Children 6–59 months with MUAC < 12.5 cm or oedema", "down"),
    ("sam", "Severe acute malnutrition (MUAC)", "Children 6–59 months with MUAC < 11.5 cm or oedema", "down"),
    ("anc4", "ANC 4+ visits", "Mothers of index children with 4 or more ANC visits", "up"),
]


def impact(raw_ind: dict, clean_ind: dict, projected_ind: dict) -> list[dict]:
    rows = []
    for key, label, definition, better in INDICATOR_META:
        r, c, pj = raw_ind.get(key), clean_ind.get(key), projected_ind.get(key)
        if not r:
            continue
        rows.append(
            {
                "key": key,
                "label": label,
                "definition": definition,
                "better": better,
                "raw": r,
                "clean": c,
                "projected": pj,
                "bias": round(r["value"] - pj["value"], 1) if r and pj and r["value"] is not None and pj["value"] is not None else None,
            }
        )
    return rows


# ---------------------------------------------------------- monitoring


def enumerator_scorecard(p: Prepared, flags: list[dict]) -> list[dict]:
    df, c = p.base, p.columns
    if not c.get("enumerator"):
        return []
    st = pd.to_datetime(df.get("start"), errors="coerce")
    en = pd.to_datetime(df.get("end"), errors="coerce")
    df = df.assign(_dur=(en - st).dt.total_seconds() / 60)
    team_med = float(df["_dur"].median()) if df["_dur"].notna().any() else None
    fl = pd.DataFrame(flags) if flags else pd.DataFrame(columns=["row", "check", "enumerator"])
    rows = []
    for name, g in df.groupby(c["enumerator"]):
        f = fl[fl["enumerator"] == name] if len(fl) else fl
        flagged_rows = f["row"].nunique() if len(f) else 0
        muac = pd.to_numeric(g[c["muac"]], errors="coerce").dropna() if c.get("muac") else pd.Series(dtype=float)
        muac = muac[muac.between(6, 26)]
        pref = round(100 * float(((muac * 10).round() % 5 == 0).mean()), 1) if len(muac) >= 10 else None
        counts = f["check"].value_counts().to_dict() if len(f) else {}
        rec = []
        if counts.get("desk_interview"):
            rec.append("Supervisor review of possible fabricated interviews")
        if counts.get("short_interview", 0) >= 3:
            rec.append("Accompany on visits; interviews are too short")
        if pref is not None and pref >= 60:
            rec.append("Refresher on MUAC measurement (readings rounded)")
        if counts.get("out_of_hours", 0) >= 2:
            rec.append("Check device clock or late-night entry")
        if counts.get("no_consent", 0) >= 2:
            rec.append("Re-brief on consent: no data without consent")
        rows.append(
            {
                "enumerator": name,
                "interviews": int(len(g)),
                "median_duration": round(float(g["_dur"].median()), 1) if g["_dur"].notna().any() else None,
                "team_median": round(team_med, 1) if team_med else None,
                "flagged_pct": round(100 * flagged_rows / len(g), 1),
                "short": int(counts.get("short_interview", 0)),
                "desk": int(counts.get("desk_interview", 0)),
                "night": int(counts.get("out_of_hours", 0)),
                "muac_rounding": pref,
                "follow_up": rec,
                "status": "act now" if counts.get("desk_interview") or len(rec) >= 2 else "watch" if rec else "good",
            }
        )
    return sorted(rows, key=lambda r: ({"act now": 0, "watch": 1, "good": 2}[r["status"]], -r["flagged_pct"]))


def readiness(flags: list[dict], status: dict) -> dict:
    total_w = sum(SEVERITY_WEIGHT[f["severity"]] for f in flags) or 1
    done_w = sum(SEVERITY_WEIGHT[f["severity"]] for f in flags if status[f["flag_id"]]["status"] != "open")
    open_by = {s: sum(1 for f in flags if f["severity"] == s and status[f["flag_id"]]["status"] == "open") for s in SEVERITY_RANK}
    waiting = sum(1 for f in flags if status[f["flag_id"]]["status"] == "awaiting verification")
    if open_by["critical"] or open_by["high"]:
        verdict, reason = "not ready", f"{open_by['critical'] + open_by['high']} critical or high-severity issues are still open."
    elif open_by["medium"] or open_by["low"] or waiting:
        minor = open_by["medium"] + open_by["low"]
        parts = [f"{minor} minor issue{'s' if minor != 1 else ''} still open"] if minor else []
        if waiting:
            parts.append(f"{waiting} record{'s' if waiting != 1 else ''} awaiting field verification")
        verdict, reason = "ready with caveats", " and ".join(parts).capitalize() + ". Report them as limitations until resolved."
    else:
        verdict, reason = "ready", "Every flag has a logged decision. The dataset is ready for analysis and sharing."
    return {"verdict": verdict, "reason": reason, "score": round(100 * done_w / total_w, 1), "open": open_by, "waiting": waiting, "total": len(flags)}


def funnel(raw: Raw, p: Prepared, clean: pd.DataFrame) -> list[dict]:
    steps = [{"label": "Received in export", "n": int(len(raw.df))}]
    steps.append({"label": "Exact duplicates removed", "n": -p.exact_duplicates})
    excl = clean[clean["_status"] == "excluded"]["_exclusion_reason"].value_counts()
    for reason, n in excl.items():
        steps.append({"label": reason, "n": -int(n)})
    steps.append({"label": "Final analysis dataset", "n": int((clean["_status"] == "included").sum()), "final": True})
    return steps


def column_profile(raw: Raw) -> list[dict]:
    out = []
    for c in raw.df.columns:
        s = raw.df[c]
        short = str(c).split("/")[-1]
        ident = bool(IDENTIFIER_PATTERN.search(short))
        out.append(
            {
                "column": str(c),
                "missing_pct": round(100 * float(s.isna().mean()), 1),
                "unique": int(s.nunique()),
                # Never send identifier values to the browser, not even as an example.
                "example": None if ident or s.dropna().empty else str(s.dropna().iloc[0])[:40],
                "identifier": ident,
                "system": short.startswith("_"),
            }
        )
    return out


