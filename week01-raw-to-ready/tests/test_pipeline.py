import io

import pandas as pd

from rtr import pipeline as P
from rtr import report
from rtr.sample import sample_export

RAW = P.raw_from_frame(sample_export(), "sample.csv", "sample")
PREP = P.prepare(RAW)
FLAGS = P.run_checks(PREP)


def test_raw_is_never_modified():
    before = RAW.df.copy()
    log = P.recommended_log(FLAGS, PREP.system_log)
    P.apply_log(PREP, log)
    pd.testing.assert_frame_equal(RAW.df, before)


def test_clean_is_reproducible_from_raw_plus_log():
    log = P.recommended_log(FLAGS, PREP.system_log)
    a = P.apply_log(P.prepare(RAW), log)
    b = P.apply_log(P.prepare(RAW), log)
    pd.testing.assert_frame_equal(a, b)


def test_identifiers_never_reach_the_analysis_copy():
    assert set(PREP.identifiers) == {"respondent_name", "phone"}
    assert not set(PREP.identifiers) & set(PREP.base.columns)


def test_planted_defects_are_flagged():
    checks = {f["check"] for f in FLAGS}
    for c in ["no_consent", "desk_interview", "duplicate_id", "muac_range", "age_range", "penta_inconsistent", "anc_range", "lga_unmapped"]:
        assert c in checks, c
    assert PREP.exact_duplicates == 24
    assert len({f["flag_id"] for f in FLAGS}) == len(FLAGS)


def test_lga_spellings_map_to_codes():
    assert PREP.base["lga_code"].notna().mean() > 0.99
    assert set(PREP.base.loc[PREP.base["lga_code"].notna(), "lga"]) <= {"Alaro", "Benin-Ofu", "Dutse Kofa", "Egbeda Nla", "Ijebu Tuntun", "Kaura Sabo", "Lafia Ora", "Mbano Ukwu"}


def test_mm_muac_is_corrected_not_dropped():
    mm = [f for f in FLAGS if f["check"] == "muac_range" and f["rec_action"] == "corrected"]
    assert mm and all(6 <= float(f["rec_new_value"]) <= 26 for f in mm)


def test_cleaning_removes_fabrication_bias():
    proj = P.apply_log(PREP, P.recommended_log(FLAGS, PREP.system_log))
    imp = {r["key"]: r for r in P.impact(P.raw_indicators(RAW, PREP.columns), P.indicators(proj, PREP.columns), P.indicators(proj, PREP.columns))}
    assert imp["penta3"]["bias"] > 2  # raw overstates coverage
    assert imp["gam"]["bias"] < 0  # raw hides malnutrition


def test_readiness_moves_with_decisions():
    st = P.flag_status(FLAGS, PREP.system_log)
    assert P.readiness(FLAGS, st)["verdict"] == "not ready"
    log = P.recommended_log(FLAGS, PREP.system_log)
    for e in log:
        if e["action"] == "sent for verification":
            e["verified_by_field"] = "Y"
    assert P.readiness(FLAGS, P.flag_status(FLAGS, log))["verdict"] == "ready"


def test_reverted_decisions_do_not_apply():
    f = next(x for x in FLAGS if x["check"] == "no_consent")
    entry = {"entry": 1, "row": f["row"], "record_id": f["record_id"], "flag_id": f["flag_id"], "check": f["check"], "variable": "ALL", "old_value": None, "new_value": None, "reason": "x", "action": "removed", "verified_by_field": "", "changed_by": "t", "date": "", "reverted": True}
    clean = P.apply_log(PREP, PREP.system_log + [entry])
    assert clean.loc[clean["row"] == f["row"], "_status"].iat[0] == "included"


def test_upload_of_kobo_xlsx_with_group_prefixes():
    buf = io.BytesIO()
    sample_export().head(40).to_excel(buf, index=False)
    raw = P.load_raw(buf.getvalue(), "export.xlsx")
    p = P.prepare(raw)
    assert p.columns["muac"] == "muac_cm" and p.columns["enumerator"] == "username"


def test_audit_pack_uses_template_columns():
    st = P.flag_status(FLAGS, PREP.system_log)
    clean = P.apply_log(PREP, PREP.system_log)
    summary = {"final_n": 1, "readiness": P.readiness(FLAGS, st), "impact": [], "funnel": [], "issues_by_type": []}
    blob = report.audit_pack(RAW, PREP, FLAGS, st, PREP.system_log, clean, summary, P.enumerator_scorecard(PREP, FLAGS), False)
    log = pd.read_excel(io.BytesIO(blob), sheet_name="cleaning_log")
    assert list(log.columns[:9]) == report.TEMPLATE_COLUMNS
    data = pd.read_excel(io.BytesIO(blob), sheet_name="clean_data")
    assert "_gps_latitude" not in data.columns and "phone" not in data.columns


def test_identifier_values_never_leave_the_server():
    prof = {c["column"]: c for c in P.column_profile(RAW)}
    assert prof["respondent/respondent_name"]["identifier"] and prof["respondent/respondent_name"]["example"] is None
    assert prof["respondent/phone"]["example"] is None


def test_reuploading_the_apps_own_clean_export_works():
    st = P.flag_status(FLAGS, PREP.system_log)
    clean = P.apply_log(PREP, PREP.system_log)
    csv = report.shareable(clean, PREP, FLAGS, st, include_gps=True).to_csv(index=False).encode()
    raw = P.load_raw(csv, "clean_export.csv")
    p = P.prepare(raw)
    assert "row_in_file" in p.base.columns and p.base["row"].is_unique
    P.run_checks(p)
